"""M119b: embeddings storage and k-NN search over memory.db.

Two layers, picked in priority order at runtime:

1. **numpy cosine** — if numpy is installed, build the candidate matrix
   in Python and do `argpartition`-style top-k. Fast enough for 10k–50k
   vectors; slower above.

2. **Pure-Python cosine** — last resort, works anywhere stdlib does.
   O(n) per query with `math.fsum` for stability. Adequate for <5k
   vectors; flag a warning when the catalogue grows past that.

Both paths share the same on-disk shape: an `embeddings_blob` table
with `ref_kind`/`ref_id`/`vec_json` columns. Vectors are stored as JSON
arrays of floats — portable across platforms.

(M215: the former sqlite-vec tier was removed — it never built the
promised `vec0` index and brute-forced `vec_distance_cosine` per row via
a SQL round-trip, i.e. slower than numpy. Add a real `vec0` mirror if
brute-force ever becomes the bottleneck.)
"""

from __future__ import annotations

import json
import logging
import math
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass

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
    """Return one of `"numpy"`, `"python"`. Result is cached after the
    first call so each subsequent connection skips the import-probe."""
    global _BACKEND
    if _BACKEND is not None:
        return _BACKEND
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
        "UPDATE embeddings_blob SET dim = ?, vec_json = ?, created_at = ? WHERE id = ?",
        (dim, payload, wall, row_id),
    )
    return row_id


def get_embedding(conn: sqlite3.Connection, *, ref_kind: str, ref_id: int) -> list[float] | None:
    ensure_embeddings_table(conn)
    row = conn.execute(
        "SELECT vec_json FROM embeddings_blob WHERE ref_kind = ? AND ref_id = ?",
        (ref_kind, ref_id),
    ).fetchone()
    if row is None:
        return None
    return json.loads(row["vec_json"])


def delete_embedding(conn: sqlite3.Connection, *, ref_kind: str, ref_id: int) -> bool:
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

    Backend selection at runtime: numpy if available, then pure-Python.
    The result shape is identical across backends.
    """
    ensure_embeddings_table(conn)
    query_list = [float(x) for x in query]
    if not query_list:
        return []
    if available_backend() == "numpy":
        return _knn_numpy(conn, query_list, ref_kind, limit)
    return _knn_python(conn, query_list, ref_kind, limit)


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
    dot = math.fsum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(math.fsum(x * x for x in a))
    nb = math.sqrt(math.fsum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 1.0
    return 1.0 - (dot / (na * nb))


__all__ = [
    "EmbeddingHit",
    "available_backend",
    "delete_embedding",
    "ensure_embeddings_table",
    "get_embedding",
    "knn",
    "upsert_embedding",
]
