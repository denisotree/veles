"""LLM Wiki — Karpathy-style three-layer knowledge base.

Since M3 the wiki always lives inside a project's state dir (typically
`<project-root>/.veles/`); the caller is responsible for passing the root.
Layout under that root:

    INDEX.md            re-generated on every write_page
    LOG.md              append-only journal
    wiki/<category>/    LLM-writable pages
        concepts/
        entities/
        sources/
    sources/<category>/ raw immutable sources

Categories are whitelisted to keep the schema predictable. M2 shipped three:
`concepts`, `entities`, `sources`. Future milestones may add `comparisons`
and `overviews` once real ingest patterns warrant them.

Path semantics:
- `rel_path` always means a path under the wiki root, starting with `wiki/`.
- Slugs are normalized to ASCII lowercase kebab-case.

INDEX.md is the source of truth for "what's in the wiki" — but it is rebuilt
from disk on every write_page call, so editing INDEX.md by hand is fine; next
write rewrites it.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from veles.core.safety import scan_for_injection
from veles.core.slug import normalize_slug as _normalize_slug

logger = logging.getLogger(__name__)

_INDEX_FILE = "INDEX.md"
_LOG_FILE = "LOG.md"
_WIKI_DIR = "wiki"
_SOURCES_DIR = "sources"
_FTS_DB = "wiki_index.db"
# M160/M161: `proposals` and `insights` removed — both are system memory
# and live in `.veles/memory/` (core/memory/artefacts.py + the `insights`
# SQL table), not user content.
_ALLOWED_CATEGORIES = (
    "concepts",
    "entities",
    "sources",
    "queries",
    "sessions",
    "self-doc",
)
_SUMMARY_CHAR_CAP = 200


@dataclass(slots=True)
class WikiPageInfo:
    rel_path: str  # e.g. "wiki/concepts/foo.md"
    category: str
    slug: str
    title: str
    summary: str


def _now_iso_z() -> str:
    return _dt.datetime.now(tz=_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_title_and_summary(content: str, fallback: str) -> tuple[str, str]:
    """Pull H1 line and first paragraph from markdown content."""
    title = fallback
    summary_lines: list[str] = []
    seen_h1 = False
    for line in content.splitlines():
        stripped = line.strip()
        if not seen_h1 and stripped.startswith("# "):
            title = stripped[2:].strip() or fallback
            seen_h1 = True
            continue
        if seen_h1 and stripped:
            if stripped.startswith("#"):
                if summary_lines:
                    break
                continue
            summary_lines.append(stripped)
            if sum(len(s) for s in summary_lines) >= _SUMMARY_CHAR_CAP:
                break
    summary = " ".join(summary_lines).strip()
    if len(summary) > _SUMMARY_CHAR_CAP:
        summary = summary[: _SUMMARY_CHAR_CAP - 1].rstrip() + "…"
    return title, summary


class Wiki:
    def __init__(self, root: Path | str) -> None:
        self._root = Path(root)
        self._fts: sqlite3.Connection | None = None
        self._fts_disabled = False

    @property
    def root(self) -> Path:
        return self._root

    def ensure_layout(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        for cat in _ALLOWED_CATEGORIES:
            (self._root / _WIKI_DIR / cat).mkdir(parents=True, exist_ok=True)
        (self._root / _SOURCES_DIR).mkdir(parents=True, exist_ok=True)

    def write_page(
        self,
        *,
        category: str,
        slug: str,
        title: str,
        content: str,
        source_url: str | None = None,
        trust: str = "authoritative",
    ) -> str:
        """Write `wiki/<category>/<slug>.md` and refresh INDEX.

        `trust` defaults to `authoritative` (curator-written, hand-authored).
        Pass `trust="external"` together with `source_url` when the content
        originated from an untrusted source (ingest of a web page, MCP tool,
        third-party doc). The frontmatter then carries `trust:` / `source_url:`
        / `fetched:` so curator and lint can apply the right priority during
        contradiction resolution (M66, §8.6).
        """
        if category not in _ALLOWED_CATEGORIES:
            raise ValueError(f"category must be one of {_ALLOWED_CATEGORIES}, got {category!r}")
        clean_slug = _normalize_slug(slug)
        self.ensure_layout()
        body = content if content.lstrip().startswith("#") else f"# {title}\n\n{content}"
        if trust != "authoritative" or source_url is not None:
            from veles.core.untrusted import trust_frontmatter

            frontmatter = trust_frontmatter(source_url or "", fetched=None) if trust == "external" else (
                f"---\ntrust: {trust}\n---\n\n"
            )
            body = frontmatter + body
        page_path = self._root / _WIKI_DIR / category / f"{clean_slug}.md"
        page_path.write_text(body, encoding="utf-8")
        self.update_index()
        rel_path = f"{_WIKI_DIR}/{category}/{clean_slug}.md"
        self._fts_upsert(rel_path, title, body)
        return rel_path

    def read_page(self, rel_path: str) -> str:
        p = self._resolve_under_root(rel_path)
        raw = p.read_text(encoding="utf-8", errors="replace")
        cleaned, _ = scan_for_injection(raw, source_label=rel_path)
        return cleaned

    def list_pages(self) -> list[WikiPageInfo]:
        self.ensure_layout()
        pages: list[WikiPageInfo] = []
        for cat in _ALLOWED_CATEGORIES:
            for md in sorted((self._root / _WIKI_DIR / cat).glob("*.md")):
                slug = md.stem
                content = md.read_text(encoding="utf-8", errors="replace")
                title, summary = _extract_title_and_summary(content, fallback=slug)
                pages.append(
                    WikiPageInfo(
                        rel_path=f"{_WIKI_DIR}/{cat}/{md.name}",
                        category=cat,
                        slug=slug,
                        title=title,
                        summary=summary,
                    )
                )
        return pages

    def search(self, query: str, *, limit: int = 10) -> list[WikiPageInfo]:
        if not query.strip():
            return []
        fts_hits = self._fts_search(query, limit=limit)
        if fts_hits is not None:
            return fts_hits
        return self._substring_search(query, limit=limit)

    def _substring_search(self, query: str, *, limit: int = 10) -> list[WikiPageInfo]:
        needle = query.lower()
        out: list[WikiPageInfo] = []
        for page in self.list_pages():
            haystack = " ".join((page.title, page.slug, page.summary)).lower()
            if needle in haystack:
                out.append(page)
                if len(out) >= limit:
                    break
        return out

    def update_index(self) -> None:
        self.ensure_layout()
        pages = self.list_pages()
        lines: list[str] = ["# INDEX", "", f"Updated: {_now_iso_z()}", ""]
        if not pages:
            lines.append("_(no pages yet)_")
        else:
            by_cat: dict[str, list[WikiPageInfo]] = {c: [] for c in _ALLOWED_CATEGORIES}
            for p in pages:
                by_cat.setdefault(p.category, []).append(p)
            for cat in _ALLOWED_CATEGORIES:
                cat_pages = by_cat.get(cat) or []
                if not cat_pages:
                    continue
                lines.append(f"## {cat}")
                lines.append("")
                for p in cat_pages:
                    summary = p.summary or "—"
                    lines.append(f"- [{p.title}]({p.rel_path}) — {summary}")
                lines.append("")
        (self._root / _INDEX_FILE).write_text("\n".join(lines) + "\n", encoding="utf-8")

    def index_text(self) -> str:
        path = self._root / _INDEX_FILE
        if not path.is_file():
            return ""
        raw = path.read_text(encoding="utf-8", errors="replace")
        cleaned, _ = scan_for_injection(raw, source_label=_INDEX_FILE)
        return cleaned

    def append_log(self, *, op: str, summary: str) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        log_path = self._root / _LOG_FILE
        entry = f"## [{_now_iso_z()}] {op}\n   {summary}\n\n"
        with log_path.open("a", encoding="utf-8") as f:
            f.write(entry)

    def save_source(self, *, category: str, slug: str, content: str, ext: str = "md") -> str:
        clean_slug = _normalize_slug(slug)
        clean_cat = _normalize_slug(category) or "misc"
        self.ensure_layout()
        cat_dir = self._root / _SOURCES_DIR / clean_cat
        cat_dir.mkdir(parents=True, exist_ok=True)
        ext_clean = ext.lstrip(".").lower() or "md"
        out_path = cat_dir / f"{clean_slug}.{ext_clean}"
        out_path.write_text(content, encoding="utf-8")
        return f"{_SOURCES_DIR}/{clean_cat}/{out_path.name}"

    def _resolve_under_root(self, rel_path: str) -> Path:
        rel = Path(rel_path)
        if rel.is_absolute():
            raise ValueError(f"rel_path must be relative, got {rel_path!r}")
        target = (self._root / rel).resolve()
        try:
            target.relative_to(self._root.resolve())
        except ValueError as exc:
            raise ValueError(f"rel_path escapes wiki root: {rel_path!r}") from exc
        return target

    # ---------- FTS5 ----------

    def reindex(self) -> int:
        """Rebuild the FTS index from disk. Returns number of pages indexed."""
        if self._fts_disabled:
            return 0
        try:
            conn = self._fts_conn()
        except sqlite3.Error as exc:
            logger.warning("FTS unavailable, skipping reindex: %s", exc)
            return 0
        return self._fts_rebuild(conn)

    def is_index_stale(self, *, max_age_sec: float = 300.0) -> bool:
        """M84: return True if the FTS db is older than max_age_sec OR any
        wiki/ file has a newer mtime than the db. Cheap freshness check so
        TUI/daemon can skip a no-op rebuild."""
        if self._fts_disabled:
            return False
        db_path = self._root / _FTS_DB
        wiki_dir = self._root / _WIKI_DIR
        if not db_path.exists():
            return wiki_dir.exists()
        try:
            db_mtime = db_path.stat().st_mtime
        except OSError:
            return True
        if not wiki_dir.exists():
            return False
        try:
            import time as _time
            if _time.time() - db_mtime > max_age_sec:
                return True
        except OSError:
            pass
        try:
            for path in wiki_dir.rglob("*.md"):
                try:
                    if path.stat().st_mtime > db_mtime:
                        return True
                except OSError:
                    continue
        except OSError:
            return False
        return False

    def reindex_if_stale(self, *, max_age_sec: float = 300.0) -> int:
        """Reindex only when `is_index_stale` says so. Returns number of
        pages reindexed, or 0 when fresh."""
        if not self.is_index_stale(max_age_sec=max_age_sec):
            return 0
        return self.reindex()

    def close(self) -> None:
        if self._fts is not None:
            self._fts.close()
            self._fts = None

    def _fts_conn(self) -> sqlite3.Connection:
        if self._fts is not None:
            return self._fts
        self._root.mkdir(parents=True, exist_ok=True)
        db_path = self._root / _FTS_DB
        conn = sqlite3.connect(str(db_path), isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(
            "CREATE VIRTUAL TABLE IF NOT EXISTS wiki_fts USING fts5("
            "rel_path UNINDEXED, title, body, "
            "tokenize = 'unicode61 remove_diacritics 1');"
        )
        self._fts = conn
        return conn

    def _fts_upsert(self, rel_path: str, title: str, body: str) -> None:
        if self._fts_disabled:
            return
        try:
            conn = self._fts_conn()
            conn.execute("DELETE FROM wiki_fts WHERE rel_path = ?", (rel_path,))
            conn.execute(
                "INSERT INTO wiki_fts (rel_path, title, body) VALUES (?, ?, ?)",
                (rel_path, title, body),
            )
        except sqlite3.Error as exc:
            logger.warning("FTS upsert failed for %s: %s", rel_path, exc)
            self._fts_disabled = True

    def _fts_rebuild(self, conn: sqlite3.Connection) -> int:
        conn.execute("DELETE FROM wiki_fts")
        count = 0
        for page in self.list_pages():
            page_path = self._root / page.rel_path
            try:
                body = page_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            conn.execute(
                "INSERT INTO wiki_fts (rel_path, title, body) VALUES (?, ?, ?)",
                (page.rel_path, page.title, body),
            )
            count += 1
        return count

    def _fts_search(self, query: str, *, limit: int) -> list[WikiPageInfo] | None:
        """Return FTS hits, or None to signal caller should fall back to substring."""
        if self._fts_disabled:
            return None
        try:
            conn = self._fts_conn()
            count = conn.execute("SELECT COUNT(*) FROM wiki_fts").fetchone()[0]
            if count == 0:
                self._fts_rebuild(conn)
            escaped = _fts_escape(query)
            if not escaped:
                return []
            rows = conn.execute(
                "SELECT rel_path FROM wiki_fts WHERE wiki_fts MATCH ? ORDER BY rank LIMIT ?",
                (escaped, limit),
            ).fetchall()
        except sqlite3.Error as exc:
            logger.warning("FTS query failed, falling back to substring: %s", exc)
            return None
        if not rows:
            return []
        pages_by_rel = {p.rel_path: p for p in self.list_pages()}
        return [pages_by_rel[r["rel_path"]] for r in rows if r["rel_path"] in pages_by_rel]


def _fts_escape(query: str) -> str:
    """Wrap each whitespace-separated token in double quotes for FTS5 MATCH safety."""
    tokens = query.split()
    return " ".join('"' + t.replace('"', '""') + '"' for t in tokens)
