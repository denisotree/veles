"""M118: Project structure cache in `memory.db`.

VISION §5.1c requires a persistent map of the project's file hierarchy
and semantic groupings — so the agent reads relevant files directly
instead of walking the whole project on each request. Hot path is
"user asks something → agent picks 3-5 files to read first" rather
than "agent runs `find .` every turn".

The cache is built incrementally:
- `Scanner(project, conn).scan()` walks the project root once, writes
  rows to `project_tree`, and updates mtimes. Subsequent scans only
  visit entries with a changed mtime (cheap on a multi-thousand-file
  repo).
- `relevant(conn, query, limit=10)` ranks entries by semantic tag +
  path-segment match against the query.

Excluded prefixes: `.veles/`, `.git/`, `node_modules/`, `.venv/`,
`__pycache__/`, plus everything matched by `.gitignore` (best effort —
we don't shell out to git, just honour `.gitignore` line-by-line for
literal patterns).

Schema lives here (not in `memory.py`) on purpose — it's an additive
table that doesn't change the `SessionStore` contract, and keeping it
local makes future M119 schema-v3 migration self-contained.
"""

from __future__ import annotations

import fnmatch
import sqlite3
from dataclasses import dataclass
from pathlib import Path

# Directory names that are always skipped, regardless of `.gitignore`.
# Tuned to dev workflows where the cache would otherwise spend 90% of
# its time hashing virtualenv internals.
_ALWAYS_EXCLUDED_DIRS = frozenset(
    {
        ".veles",
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".eggs",
        "dist",
        "build",
        ".idea",
        ".vscode",
    }
)


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS project_tree (
    rel_path        TEXT PRIMARY KEY,
    kind            TEXT NOT NULL,         -- 'dir' | 'file'
    parent_path     TEXT,                  -- NULL for root
    semantic_tag    TEXT,                  -- 'src' | 'tests' | 'docs' | 'data' | 'config' | NULL
    mtime           REAL NOT NULL,         -- last filesystem mtime we saw
    size            INTEGER NOT NULL,      -- 0 for dirs, byte count for files
    last_scanned_at REAL NOT NULL,         -- wallclock of last scan write
    FOREIGN KEY(parent_path) REFERENCES project_tree(rel_path) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_project_tree_kind
    ON project_tree(kind);

CREATE INDEX IF NOT EXISTS idx_project_tree_tag
    ON project_tree(semantic_tag) WHERE semantic_tag IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_project_tree_parent
    ON project_tree(parent_path);
"""


@dataclass(frozen=True, slots=True)
class TreeEntry:
    """One row of `project_tree`. Read API result type."""

    rel_path: str
    kind: str
    parent_path: str | None
    semantic_tag: str | None
    mtime: float
    size: int


def ensure_table(conn: sqlite3.Connection) -> None:
    """Create the `project_tree` table and its indexes if absent.
    Idempotent — callers can run it on every connection open."""
    conn.executescript(_SCHEMA_SQL)


# ---------- semantic tagger ----------


def _semantic_tag(rel_path: str, kind: str) -> str | None:
    """Heuristic rule-based classifier. Returns None when no rule fires.

    Rules are intentionally simple: substring/prefix match against the
    first path segment. Sophisticated tagging (e.g. inferring "src" by
    looking at file extensions) is M118 follow-up.
    """
    if not rel_path:
        return None
    first = rel_path.split("/", 1)[0].lower()
    if first in {"src", "lib", "source"}:
        return "src"
    if first in {"tests", "test", "spec", "specs"}:
        return "tests"
    if first in {"docs", "doc", "documentation"}:
        return "docs"
    if first in {"data", "datasets", "fixtures"}:
        return "data"
    if first in {"config", "configs", "etc", "conf"}:
        return "config"
    if first in {"scripts", "tools", "bin"}:
        return "scripts"
    # Top-level files: tag by name pattern.
    if kind == "file" and "/" not in rel_path:
        name = rel_path.lower()
        if name in {"readme.md", "readme.rst", "readme"}:
            return "docs"
        if name in {"agents.md", "vision.md", "tasks.md", "milestones.md"}:
            return "docs"
        if name.endswith((".toml", ".yaml", ".yml", ".ini", ".cfg")):
            return "config"
    return None


# ---------- scanner ----------


@dataclass
class ScanReport:
    """Summary of one `scan()` invocation — useful for logging and tests."""

    scanned: int = 0
    added: int = 0
    updated: int = 0
    removed: int = 0


class Scanner:
    """Walks the project root, writes rows to `project_tree`. Designed
    to be cheap on re-scan: it compares filesystem mtime against the
    last value persisted and only updates rows that changed.

    Always-excluded directories (`.veles/`, `.git/`, …) are skipped
    eagerly by name during the walk. `.gitignore` patterns are honoured
    line-by-line as literal fnmatch globs (no negation / re_compile);
    this catches the common 90% case without dragging in a git
    dependency.
    """

    def __init__(
        self,
        root: Path,
        conn: sqlite3.Connection,
        *,
        now: float | None = None,
    ) -> None:
        self._root = root.resolve()
        self._conn = conn
        self._now = now  # injectable for deterministic tests
        ensure_table(conn)
        self._gitignore: list[str] = _load_gitignore(self._root)

    def scan(self) -> ScanReport:
        """Walk the project root, upsert rows for every visible entry,
        delete rows for paths that no longer exist."""
        import time

        report = ScanReport()
        wall = self._now if self._now is not None else time.time()
        seen: set[str] = set()

        # Upsert in dependency order — directories first so their FK
        # parent_path resolves cleanly when files reference them.
        for rel, abs_path, kind in self._walk():
            report.scanned += 1
            seen.add(rel)
            try:
                stat = abs_path.stat()
            except OSError:
                continue
            mtime = stat.st_mtime
            size = stat.st_size if kind == "file" else 0
            parent = _parent_path(rel)
            tag = _semantic_tag(rel, kind)

            existing = self._conn.execute(
                "SELECT mtime FROM project_tree WHERE rel_path = ?", (rel,)
            ).fetchone()
            if existing is None:
                self._conn.execute(
                    "INSERT INTO project_tree("
                    " rel_path, kind, parent_path, semantic_tag,"
                    " mtime, size, last_scanned_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (rel, kind, parent, tag, mtime, size, wall),
                )
                report.added += 1
            elif abs(existing["mtime"] - mtime) > 1e-6:
                self._conn.execute(
                    "UPDATE project_tree"
                    " SET kind = ?, parent_path = ?, semantic_tag = ?,"
                    "     mtime = ?, size = ?, last_scanned_at = ?"
                    " WHERE rel_path = ?",
                    (kind, parent, tag, mtime, size, wall, rel),
                )
                report.updated += 1

        # Drop rows for paths no longer on disk. We do this after the
        # walk so an interruption mid-scan can't leave the table in a
        # state that under-reports project contents.
        rows = self._conn.execute("SELECT rel_path FROM project_tree").fetchall()
        all_rel = {row["rel_path"] for row in rows}
        gone = all_rel - seen
        if gone:
            self._conn.executemany(
                "DELETE FROM project_tree WHERE rel_path = ?",
                [(r,) for r in gone],
            )
            report.removed = len(gone)

        return report

    def _walk(self):
        """Yield `(rel_path, abs_path, kind)` for every visible entry,
        breadth-ish-first so parents always precede children. `rel_prefix`
        is the parent's rel_path *without* trailing slash — we add the
        separator at concatenation time."""
        stack: list[tuple[Path, str]] = [(self._root, "")]
        while stack:
            current, rel_prefix = stack.pop()
            try:
                entries = sorted(current.iterdir(), key=lambda p: p.name)
            except OSError:
                continue
            for entry in entries:
                name = entry.name
                rel = name if not rel_prefix else f"{rel_prefix}/{name}"
                if entry.is_dir() and not entry.is_symlink():
                    if name in _ALWAYS_EXCLUDED_DIRS:
                        continue
                    if self._ignored(rel + "/"):
                        continue
                    yield rel, entry, "dir"
                    stack.append((entry, rel))
                elif entry.is_file() and not entry.is_symlink():
                    if self._ignored(rel):
                        continue
                    yield rel, entry, "file"

    def _ignored(self, rel: str) -> bool:
        for pattern in self._gitignore:
            if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(rel, pattern.rstrip("/")):
                return True
        return False


def _load_gitignore(root: Path) -> list[str]:
    path = root / ".gitignore"
    if not path.is_file():
        return []
    out: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        out.append(line)
    return out


def _parent_path(rel: str) -> str | None:
    if "/" not in rel:
        return None
    return rel.rsplit("/", 1)[0]


# ---------- recall API ----------


def relevant(
    conn: sqlite3.Connection, query: str, *, limit: int = 10
) -> list[TreeEntry]:
    """Return the entries whose `semantic_tag` or `rel_path` best matches
    `query`. Ranking is a simple weighted score:

    - exact path-segment match (+3)
    - semantic_tag substring in query (+2)
    - any path-segment substring of a query token (+1)
    - file beats dir on ties (small +0.1)

    Sufficient for the 80% "agent wants 5 candidate files" use case;
    M118 follow-up may add embedding-based ranking once M119 lands
    sqlite-vec.
    """
    ensure_table(conn)
    rows = conn.execute(
        "SELECT rel_path, kind, parent_path, semantic_tag, mtime, size"
        " FROM project_tree"
    ).fetchall()
    if not rows:
        return []
    tokens = [t.lower() for t in _tokenise(query) if t]
    scored: list[tuple[float, TreeEntry]] = []
    for row in rows:
        entry = TreeEntry(
            rel_path=row["rel_path"],
            kind=row["kind"],
            parent_path=row["parent_path"],
            semantic_tag=row["semantic_tag"],
            mtime=row["mtime"],
            size=row["size"],
        )
        score = _score(entry, tokens)
        if score > 0:
            scored.append((score, entry))
    scored.sort(key=lambda x: (-x[0], x[1].rel_path))
    return [e for _, e in scored[:limit]]


def _tokenise(query: str) -> list[str]:
    """Split on non-alphanumeric so `tests/test_x.py` → [tests, test, x, py]."""
    import re

    return [t for t in re.split(r"[^a-zA-Z0-9_]+", query.lower()) if t]


def _score(entry: TreeEntry, tokens: list[str]) -> float:
    if not tokens:
        return 0.0
    path_lower = entry.rel_path.lower()
    segments = path_lower.replace("/", " ").replace("_", " ").replace("-", " ").split()
    seg_set = set(segments)
    score = 0.0
    for token in tokens:
        if token in seg_set:
            score += 3.0
        elif any(token in seg for seg in segments):
            score += 1.0
        if entry.semantic_tag and token in entry.semantic_tag:
            score += 2.0
    if entry.kind == "file" and score > 0:
        score += 0.1
    return score


def relevant_semantic(
    conn: sqlite3.Connection, query: str, *, limit: int = 10
) -> list[TreeEntry]:
    """Embedding-aware variant of `relevant`.

    Falls back to `relevant(...)` (token-based) when no embedding
    adapter is registered, when the adapter raises, or when the
    project tree is empty. Never crashes — the upgrade path is
    transparent.

    Strategy:
    1. Resolve the embedding adapter via
       `veles.modules.get_embedding_adapter()`.
    2. Embed the query once.
    3. For each TreeEntry, build a short text signature
       (rel_path + semantic_tag + kind) and embed it.
       *Optimisation note:* a real production path caches per-entry
       embeddings in `embeddings_blob` keyed on `(ref_kind="path",
       ref_id=<some rowid>)`. M118c-final adds that; this MVP
       embeds on every call. Affordable at ≤500 entries; switch on
       the cache once project_tree rows exceed that.
    4. Cosine-rank, take top-`limit`.

    Returns `list[TreeEntry]` ordered by descending similarity.
    """
    from veles.modules import EmbeddingError, get_embedding_adapter

    adapter = get_embedding_adapter()
    if adapter is None:
        return relevant(conn, query, limit=limit)
    if not query.strip():
        return []

    ensure_table(conn)
    rows = conn.execute(
        "SELECT rel_path, kind, parent_path, semantic_tag, mtime, size"
        " FROM project_tree"
    ).fetchall()
    if not rows:
        return []

    entries = [
        TreeEntry(
            rel_path=r["rel_path"],
            kind=r["kind"],
            parent_path=r["parent_path"],
            semantic_tag=r["semantic_tag"],
            mtime=r["mtime"],
            size=r["size"],
        )
        for r in rows
    ]
    signatures = [_entry_signature(e) for e in entries]

    try:
        query_vec = adapter.embed([query])[0]
        entry_vecs = adapter.embed(signatures)
    except EmbeddingError:
        # Network / model failure → fall back transparently.
        return relevant(conn, query, limit=limit)

    scored = [
        (_cosine(query_vec, vec), entry)
        for vec, entry in zip(entry_vecs, entries, strict=True)
    ]
    scored.sort(key=lambda x: (-x[0], x[1].rel_path))
    return [e for _, e in scored[:limit]]


def _entry_signature(entry: TreeEntry) -> str:
    """Short text the embedder sees per project_tree entry. Path
    segments + semantic tag + kind. Kept brief so embedding cost
    scales linearly in entry count, not in file size."""
    tag = entry.semantic_tag or "untagged"
    return f"{entry.kind} {tag}: {entry.rel_path.replace('/', ' ')}"


def _cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity in [-1, 1]. Pure Python — same shape as
    the fallback in `memory_vector._cosine_distance` but returns
    *similarity* (higher is better) so the sort key is `-score`."""
    import math

    if not a or not b or len(a) != len(b):
        return 0.0
    dot = math.fsum(x * y for x, y in zip(a, b))
    na = math.sqrt(math.fsum(x * x for x in a))
    nb = math.sqrt(math.fsum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


__all__ = [
    "ScanReport",
    "Scanner",
    "TreeEntry",
    "ensure_table",
    "relevant",
    "relevant_semantic",
]
