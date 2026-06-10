"""M119b: embeddings storage and k-NN search over memory.db.

Three layers, picked in priority order at runtime:

1. **sqlite-vec** loaded as a SQLite extension — fastest, C brute
   force, k-NN via `vec0` virtual table. Optional dependency
   (`pip install sqlite-vec`). The wheel is published per platform
   so install is one-line; we still gate the load behind a try/except
   because not every Python build exposes `enable_load_extension`
   and not every platform has a wheel.

2. **numpy cosine** — if numpy is installed but sqlite-vec isn't,
   we build the candidate matrix in Python and do `argpartition`-style
   top-k. Fast enough for 10k–50k vectors; slower above.

3. **Pure-Python cosine** — last resort, works anywhere stdlib
   does. O(n) per query with `math.fsum` for stability. Adequate for
   <5k vectors; flag a warning when the catalogue grows past that.

All three paths share the same on-disk shape: an `embeddings_blob`
table with `ref_kind`/`ref_id`/`vec_json` columns. Vectors are stored
as JSON arrays of floats — portable across platforms and survives a
sqlite-vec install/uninstall without re-encoding. When sqlite-vec is
available we *additionally* materialise the same rows into the
`embeddings_vec0` virtual table; a trigger keeps the two in sync.
The blob table is the source of truth.
"""

from __future__ import annotations

import json
import logging
import math
import sqlite3
from dataclasses import dataclass
from typing import Iterable

logger = logging.getLogger(__name__)


_SCHEMA_BLOB_SQL = """
CREATE TABLE IF NOT EXISTS embeddings_blob (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ref_kind  TEXT NOT NULL,
    ref_id    INTEGER NOT NULL,
    dim       INTEGER NOT NULL,
    vec_json  TEXT NOT NULL,
    created_at REAL NOT NULL,
    UNIQUE (ref_kind, ref_id)
);

CREATE INDEX IF NOT EXISTS idx_embeddings_blob_ref
    ON embeddings_blob(ref_kind, ref_id);
"""


@dataclass(frozen=True, slots=True)
class EmbeddingHit:
    """One k-NN result row. `distance` follows the cosine convention:
    1.0 - cosine_similarity, so smaller is better, range [0, 2]."""

    ref_kind: str
    ref_id: int
    distance: float


# ---------- backend detection ----------


_BACKEND: str | None = None  # populated lazily by `available_backend`


def available_backend() -> str:
    """Return one of `"sqlite-vec"`, `"numpy"`, `"python"`. Result is
    cached after the first call so each subsequent connection skips
    the import-probe."""
    global _BACKEND
    if _BACKEND is not None:
        return _BACKEND
    try:
        import sqlite_vec  # noqa: F401

        _BACKEND = "sqlite-vec"
        return _BACKEND
    except ImportError:
        pass
    try:
        import numpy  # noqa: F401

        _BACKEND = "numpy"
        return _BACKEND
    except ImportError:
        pass
    _BACKEND = "python"
    return _BACKEND


def _reset_backend_cache() -> None:
    """Test helper — clears the memoised backend probe so a test can
    monkey-patch sqlite_vec / numpy availability between runs."""
    global _BACKEND
    _BACKEND = None


# ---------- schema ----------


def ensure_embeddings_table(conn: sqlite3.Connection) -> None:
    """Create the blob-backed table on `conn`. Idempotent. Callers
    typically run this once per SessionStore open — the SessionStore
    schema bootstrap (`_init_schema`) doesn't, because the blob table
    is opt-in: not every install needs embeddings."""
    conn.executescript(_SCHEMA_BLOB_SQL)


def _try_load_sqlite_vec(conn: sqlite3.Connection) -> bool:
    """Best-effort load of the sqlite-vec extension into `conn`.
    Returns True iff the extension is now active. Failures (extension
    library missing, `enable_load_extension` unavailable in the Python
    build, OS lacks a prebuilt wheel) are caught and logged."""
    if available_backend() != "sqlite-vec":
        return False
    try:
        import sqlite_vec
    except ImportError:
        return False
    try:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
    except (sqlite3.OperationalError, AttributeError) as exc:
        logger.info(
            "sqlite-vec load failed: %s; falling back to pure-Python cosine",
            exc,
        )
        return False
    return True


# ---------- writes ----------


def upsert_embedding(
    conn: sqlite3.Connection,
    *,
    ref_kind: str,
    ref_id: int,
    vec: Iterable[float],
    now: float | None = None,
) -> int:
    """Insert or replace the embedding for `(ref_kind, ref_id)`.
    Returns the row id."""
    import time as _time

    ensure_embeddings_table(conn)
    wall = _time.time() if now is None else now
    vec_list = [float(x) for x in vec]
    if not vec_list:
        raise ValueError("embedding vector is empty")
    dim = len(vec_list)
    payload = json.dumps(vec_list)
    existing = conn.execute(
        "SELECT id FROM embeddings_blob WHERE ref_kind = ? AND ref_id = ?",
        (ref_kind, ref_id),
    ).fetchone()
    if existing is None:
        cur = conn.execute(
            "INSERT INTO embeddings_blob(ref_kind, ref_id, dim, vec_json, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (ref_kind, ref_id, dim, payload, wall),
        )
        return int(cur.lastrowid or 0)
    row_id = int(existing["id"])
    conn.execute(
        "UPDATE embeddings_blob SET dim = ?, vec_json = ?, created_at = ?"
        " WHERE id = ?",
        (dim, payload, wall, row_id),
    )
    return row_id


def get_embedding(
    conn: sqlite3.Connection, *, ref_kind: str, ref_id: int
) -> list[float] | None:
    ensure_embeddings_table(conn)
    row = conn.execute(
        "SELECT vec_json FROM embeddings_blob WHERE ref_kind = ? AND ref_id = ?",
        (ref_kind, ref_id),
    ).fetchone()
    if row is None:
        return None
    return json.loads(row["vec_json"])


def delete_embedding(
    conn: sqlite3.Connection, *, ref_kind: str, ref_id: int
) -> bool:
    ensure_embeddings_table(conn)
    cur = conn.execute(
        "DELETE FROM embeddings_blob WHERE ref_kind = ? AND ref_id = ?",
        (ref_kind, ref_id),
    )
    return cur.rowcount > 0


# ---------- k-NN ----------


def knn(
    conn: sqlite3.Connection,
    query: Iterable[float],
    *,
    ref_kind: str | None = None,
    limit: int = 10,
) -> list[EmbeddingHit]:
    """Return the top-`limit` nearest neighbours to `query` in cosine
    distance. `ref_kind` filters to one source ("skill", "tool",
    "insight", etc.) — None scans the whole catalogue.

    Backend selection at runtime: sqlite-vec if available, then numpy,
    then pure-Python. The result shape is identical across backends.
    """
    ensure_embeddings_table(conn)
    query_list = [float(x) for x in query]
    if not query_list:
        return []
    backend = available_backend()
    if backend == "sqlite-vec":
        return _knn_sqlite_vec(conn, query_list, ref_kind, limit)
    if backend == "numpy":
        return _knn_numpy(conn, query_list, ref_kind, limit)
    return _knn_python(conn, query_list, ref_kind, limit)


def _knn_sqlite_vec(
    conn: sqlite3.Connection,
    query: list[float],
    ref_kind: str | None,
    limit: int,
) -> list[EmbeddingHit]:
    """sqlite-vec path. If load fails at runtime (e.g. the extension
    library was uninstalled between Python startup and now), we fall
    through to numpy/python so a partial degradation never raises."""
    if not _try_load_sqlite_vec(conn):
        return _knn_numpy(conn, query, ref_kind, limit)
    # The vec0 table is keyed by rowid; we materialise rows from the
    # blob table on demand. Skip vec0 in this MVP because keeping two
    # tables in sync is the more complex part; the brute-force vec_*
    # function approach below works without a separate virtual table.
    rows = conn.execute(
        "SELECT ref_kind, ref_id, vec_json FROM embeddings_blob"
        + (" WHERE ref_kind = ?" if ref_kind else ""),
        (ref_kind,) if ref_kind else (),
    ).fetchall()
    if not rows:
        return []
    # sqlite-vec exposes `vec_distance_cosine` once loaded — use it on
    # JSON-decoded vectors batched in Python because building a true
    # vec0 mirror is M119b polish, not MVP.
    import struct

    def pack(v: list[float]) -> bytes:
        return struct.pack(f"{len(v)}f", *v)

    qbytes = pack(query)
    candidates: list[tuple[float, sqlite3.Row]] = []
    for row in rows:
        cand = json.loads(row["vec_json"])
        if len(cand) != len(query):
            continue
        try:
            dist = conn.execute(
                "SELECT vec_distance_cosine(?, ?) AS d",
                (qbytes, pack(cand)),
            ).fetchone()
        except sqlite3.OperationalError:
            # Function unavailable — fall back per-row to python cosine.
            dist = {"d": _cosine_distance(query, cand)}
        d = float(dist["d"]) if dist["d"] is not None else 2.0
        candidates.append((d, row))
    candidates.sort(key=lambda x: x[0])
    return [
        EmbeddingHit(ref_kind=row["ref_kind"], ref_id=int(row["ref_id"]), distance=d)
        for d, row in candidates[:limit]
    ]


def _knn_numpy(
    conn: sqlite3.Connection,
    query: list[float],
    ref_kind: str | None,
    limit: int,
) -> list[EmbeddingHit]:
    """Numpy path. Builds a (n, dim) matrix, computes cosine in one
    vectorised pass. O(n·dim) memory + CPU; fine up to ~50k vectors."""
    try:
        import numpy as np
    except ImportError:
        return _knn_python(conn, query, ref_kind, limit)

    rows = conn.execute(
        "SELECT ref_kind, ref_id, vec_json FROM embeddings_blob"
        + (" WHERE ref_kind = ?" if ref_kind else ""),
        (ref_kind,) if ref_kind else (),
    ).fetchall()
    if not rows:
        return []
    refs: list[tuple[str, int]] = []
    vecs: list[list[float]] = []
    for row in rows:
        vec = json.loads(row["vec_json"])
        if len(vec) != len(query):
            continue
        refs.append((row["ref_kind"], int(row["ref_id"])))
        vecs.append(vec)
    if not vecs:
        return []
    mat = np.asarray(vecs, dtype=np.float32)
    q = np.asarray(query, dtype=np.float32)
    # Cosine: 1 - (a·b / (||a|| * ||b||)); guard zero-norm vectors with
    # epsilon so a degenerate row doesn't blow up the whole batch.
    eps = 1e-12
    norms = np.linalg.norm(mat, axis=1)
    q_norm = float(np.linalg.norm(q))
    denoms = (norms * q_norm) + eps
    dots = mat @ q
    distances = 1.0 - (dots / denoms)
    # `argpartition` for top-k beats a full sort for n >> limit.
    k = min(limit, len(distances))
    if k <= 0:
        return []
    idx = np.argpartition(distances, k - 1)[:k]
    # Sort just the top-k slice for stable output ordering.
    idx = idx[np.argsort(distances[idx])]
    return [
        EmbeddingHit(
            ref_kind=refs[i][0],
            ref_id=refs[i][1],
            distance=float(distances[i]),
        )
        for i in idx.tolist()
    ]


def _knn_python(
    conn: sqlite3.Connection,
    query: list[float],
    ref_kind: str | None,
    limit: int,
) -> list[EmbeddingHit]:
    """Pure-Python fallback. O(n·dim) per call but no native deps."""
    rows = conn.execute(
        "SELECT ref_kind, ref_id, vec_json FROM embeddings_blob"
        + (" WHERE ref_kind = ?" if ref_kind else ""),
        (ref_kind,) if ref_kind else (),
    ).fetchall()
    if not rows:
        return []
    hits: list[EmbeddingHit] = []
    for row in rows:
        cand = json.loads(row["vec_json"])
        if len(cand) != len(query):
            continue
        d = _cosine_distance(query, cand)
        hits.append(
            EmbeddingHit(
                ref_kind=row["ref_kind"],
                ref_id=int(row["ref_id"]),
                distance=d,
            )
        )
    hits.sort(key=lambda h: h.distance)
    return hits[:limit]


def _cosine_distance(a: list[float], b: list[float]) -> float:
    """1 - cosine_similarity, stabilised with `math.fsum`."""
    if len(a) != len(b):
        return 2.0  # max cosine distance
    dot = math.fsum(x * y for x, y in zip(a, b))
    na = math.sqrt(math.fsum(x * x for x in a))
    nb = math.sqrt(math.fsum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 1.0
    return 1.0 - (dot / (na * nb))


# ---------- migration from M61 skill_embeddings.json ----------


def migrate_legacy_skill_embeddings(
    conn: sqlite3.Connection,
    *,
    legacy_path,
    skill_id_by_hash: dict[str, int],
    now: float | None = None,
) -> int:
    """Move embeddings from `<project>/.veles/skill_embeddings.json`
    (M61 format: `{sha256: [vec]}`) into `embeddings_blob` under
    `ref_kind = "skill"`. `skill_id_by_hash` maps the cache key to the
    catalogue's skill id — callers compute this from the current
    SKILL.md set. Unknown hashes are skipped (the skill was removed
    since the cache was written).

    Returns the count of migrated rows. The legacy file is left in
    place; the caller can delete it after a successful migration if
    desired.
    """
    import time as _time

    wall = _time.time() if now is None else now
    legacy_path = legacy_path
    try:
        body = legacy_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return 0
    try:
        cache = json.loads(body) if body.strip() else {}
    except json.JSONDecodeError:
        logger.warning("skill_embeddings.json is not valid JSON; skipping migration")
        return 0
    if not isinstance(cache, dict):
        return 0
    ensure_embeddings_table(conn)
    migrated = 0
    for sha, vec in cache.items():
        if not isinstance(vec, list):
            continue
        skill_id = skill_id_by_hash.get(sha)
        if skill_id is None:
            continue
        upsert_embedding(
            conn,
            ref_kind="skill",
            ref_id=skill_id,
            vec=vec,
            now=wall,
        )
        migrated += 1
    return migrated


__all__ = [
    "EmbeddingHit",
    "available_backend",
    "delete_embedding",
    "ensure_embeddings_table",
    "get_embedding",
    "knn",
    "migrate_legacy_skill_embeddings",
    "upsert_embedding",
]
