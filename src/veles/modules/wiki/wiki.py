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

Allowed category roots = the core defaults (`concepts`, `entities`, `sources`,
`queries`, `sessions`, `self-doc`) plus the active layout pack's
`[layout.wiki].categories`. A category may be a nested path (`projects/work`),
so the wiki layout is extensible for iterative data (diary/tasks/projects).

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
# Core categories always present regardless of layout pack (curator writes
# `sessions`, self-doc writes `self-doc`, ingest writes concepts/entities/sources).
_DEFAULT_CATEGORIES = (
    "concepts",
    "entities",
    "sources",
    "queries",
    "sessions",
    "self-doc",
)
_SUMMARY_CHAR_CAP = 200


def project_categories_path(root: Path) -> Path:
    """Where a project declares its OWN wiki categories. Lives in the always-
    writable `.veles/`, so the agent can extend the structure at runtime — the
    framework ships no project-specific schema."""
    return root / ".veles" / "wiki.toml"


def normalize_category(name: str) -> str | None:
    """Normalize a (possibly nested) category like `Projects/Work` → `projects/work`.
    Returns None if empty or a segment is unsafe (`..`, non-slug)."""
    parts = [p for p in name.strip().strip("/").split("/") if p]
    if not parts or any(p == ".." for p in parts):
        return None
    norm = [_normalize_slug(p) for p in parts]
    if any(not p for p in norm):
        return None
    return "/".join(norm)


def read_project_categories(root: Path) -> list[str]:
    """The project-local category declarations (`.veles/wiki.toml`). Best-effort."""
    path = project_categories_path(root)
    if not path.is_file():
        return []
    try:
        import tomllib

        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except Exception:
        return []
    cats = data.get("categories")
    if not isinstance(cats, list):
        return []
    out: list[str] = []
    for c in cats:
        if isinstance(c, str):
            norm = normalize_category(c)
            if norm:
                out.append(norm)
    return out


def add_project_category(root: Path, name: str) -> tuple[bool, str]:
    """Declare a new project-local wiki category, persisting to `.veles/wiki.toml`.
    Returns (added, category-or-error). Idempotent; refuses core defaults and
    already-declared categories (added=False, not an error)."""
    norm = normalize_category(name)
    if norm is None:
        return False, f"<error: invalid category name {name!r}>"
    if norm in _DEFAULT_CATEGORIES:
        return False, norm  # a core category — already available
    existing = read_project_categories(root)
    if norm in existing:
        return False, norm
    existing.append(norm)
    path = project_categories_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Project-local wiki categories — declared by you / the agent.",
        "# The framework ships no project-specific schema; yours lives here.",
        "categories = [",
        *[f'    "{c}",' for c in existing],
        "]",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True, norm


def _resolve_wiki_categories(root: Path) -> tuple[str, ...]:
    """Allowed category roots = core defaults + the active layout pack's
    `[layout.wiki].categories` + the PROJECT's own `.veles/wiki.toml` categories.

    The project-local source is what keeps schema out of the framework: the
    builtin `llm-wiki` pack ships only the generic categories; diary/tasks/
    projects and any other project-specific structure are declared per-project.
    Best-effort — any failure degrades to whatever resolved, never breaks a
    write."""
    resolved: list[str] = list(_DEFAULT_CATEGORIES)

    def _add(cats: object) -> None:
        if not isinstance(cats, (list, tuple)):
            return
        for c in cats:
            if isinstance(c, str) and c and c not in resolved:
                resolved.append(c)

    try:
        import tomllib

        name = "llm-wiki"
        proj_toml = root / ".veles" / "project.toml"
        if proj_toml.is_file():
            with proj_toml.open("rb") as fh:
                data = tomllib.load(fh)
            n = (data.get("project") or {}).get("layout")
            if isinstance(n, str) and n.strip():
                name = n.strip()
        from veles.core.layout.discovery import find_layout

        pack = find_layout(name, project=None)
        if pack is not None:
            _add(pack.manifest.wiki_categories)
    except Exception:
        pass
    _add(read_project_categories(root))
    return tuple(resolved)


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
    def __init__(self, root: Path | str, *, categories: tuple[str, ...] | None = None) -> None:
        self._root = Path(root)
        self._fts: sqlite3.Connection | None = None
        self._fts_disabled = False
        # Allowed category roots: explicit override (tests) or resolved from the
        # active layout pack (defaults plus pack extras). Resolved lazily, once.
        self._categories_override = categories
        self._categories_resolved: tuple[str, ...] | None = None

    @property
    def root(self) -> Path:
        return self._root

    def categories(self) -> tuple[str, ...]:
        """The allowed wiki category roots for this project's layout pack."""
        if self._categories_override is not None:
            return self._categories_override
        if self._categories_resolved is None:
            self._categories_resolved = _resolve_wiki_categories(self._root)
        return self._categories_resolved

    def _validate_category(self, category: str) -> str:
        """Normalize + validate a (possibly nested) category like `projects/work`.
        Its first segment must be a declared category root; every segment is
        slug-normalized. Raises ValueError otherwise."""
        parts = [p for p in category.strip().strip("/").split("/") if p]
        if not parts:
            raise ValueError("category must be non-empty")
        allowed = self.categories()
        if parts[0] not in allowed:
            raise ValueError(f"category root must be one of {allowed}, got {category!r}")
        norm = [_normalize_slug(p) for p in parts]
        if any(not p for p in norm):
            raise ValueError(f"category has an invalid segment: {category!r}")
        return "/".join(norm)

    def ensure_layout(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        for cat in self.categories():
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
        category = self._validate_category(category)
        clean_slug = _normalize_slug(slug)
        self.ensure_layout()
        body = content if content.lstrip().startswith("#") else f"# {title}\n\n{content}"
        if trust != "authoritative" or source_url is not None:
            from veles.core.untrusted import trust_frontmatter

            if trust == "external":
                frontmatter = trust_frontmatter(source_url or "", fetched=None)
            else:
                frontmatter = f"---\ntrust: {trust}\n---\n\n"
            body = frontmatter + body
        page_path = self._root / _WIKI_DIR / category / f"{clean_slug}.md"
        page_path.parent.mkdir(parents=True, exist_ok=True)  # nested category (projects/work)
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
        wiki_base = self._root / _WIKI_DIR
        for cat in self.categories():
            # Recurse so nested substructure (e.g. projects/work/*.md) is listed;
            # the page's `category` is its parent dir relative to wiki/.
            for md in sorted((wiki_base / cat).rglob("*.md")):
                nested_cat = md.parent.relative_to(wiki_base).as_posix()
                slug = md.stem
                content = md.read_text(encoding="utf-8", errors="replace")
                title, summary = _extract_title_and_summary(content, fallback=slug)
                pages.append(
                    WikiPageInfo(
                        rel_path=f"{_WIKI_DIR}/{nested_cat}/{md.name}",
                        category=nested_cat,
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
            by_cat: dict[str, list[WikiPageInfo]] = {}
            for p in pages:
                by_cat.setdefault(p.category, []).append(p)
            # Emit declared roots in pack order; within each, its nested
            # sub-categories sorted so the index is deterministic.
            for root_cat in self.categories():
                subcats = sorted(c for c in by_cat if c == root_cat or c.startswith(f"{root_cat}/"))
                for cat in subcats:
                    lines.append(f"## {cat}")
                    lines.append("")
                    for p in sorted(by_cat[cat], key=lambda x: x.slug):
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
