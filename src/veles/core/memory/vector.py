"""M119b: embeddings storage and k-NN search over memory.db.

Two layers, picked in priority order at runtime:

1. **numpy cosine** — if numpy is installed, build the candidate matrix
   in Python and do `argpartition`-style top-k. Fast enough for 10k–50k
   vectors; slower above.

2. **Pure-Python cosine** — last resort, works anywhere stdlib does.
   O(n) per query with `math.fsum` for stability. Adequate for <5k
   vectors; flag a warning when the catalogue grows past that.

Both paths share the same on-disk shape: an `embeddings_blob` table
with `ref_kind`/`ref_id`/`vec_blob` columns.

M263a replaced the original JSON storage with packed little-endian float32.
JSON cost roughly 12 bytes per dimension against 4, and — the part that
actually hurt — every row had to be parsed by `json.loads` on every query,
because a brute-force scan reads all of them. At the 768 dimensions the
default local embedder emits, a million rows is ~8.6 GB of JSON text to parse
per query versus 2.86 GB of bytes to read. Little-endian is explicit rather
than native so a database file stays readable after it moves machines.

(M215: the former sqlite-vec tier was removed — it never built the
promised `vec0` index and brute-forced `vec_distance_cosine` per row via
a SQL round-trip, i.e. slower than numpy. Add a real `vec0` mirror if
brute-force ever becomes the bottleneck.)
"""

from __future__ import annotations

import contextlib
import logging
import math
import sqlite3
import struct
from collections.abc import Iterable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


_SCHEMA_BLOB_SQL = """
CREATE TABLE IF NOT EXISTS embeddings_blob (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ref_kind  TEXT NOT NULL,
    ref_id    INTEGER NOT NULL,
    dim       INTEGER NOT NULL,
    vec_blob  BLOB NOT NULL,
    created_at REAL NOT NULL,
    UNIQUE (ref_kind, ref_id)
);

CREATE INDEX IF NOT EXISTS idx_embeddings_blob_ref
    ON embeddings_blob(ref_kind, ref_id);
"""

# Rows converted per statement while migrating a pre-M263a database. Small
# enough that a huge table does not build one giant transaction, large enough
# that the round-trips do not dominate.
_MIGRATE_BATCH = 2_000


def pack(vec: Iterable[float]) -> bytes:
    """Little-endian float32 wire format for one vector."""
    values = [float(x) for x in vec]
    return struct.pack(f"<{len(values)}f", *values)


def unpack(blob: bytes) -> list[float]:
    return list(struct.unpack(f"<{len(blob) // 4}f", blob))


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
    is opt-in: not every install needs embeddings.

    The M263a JSON→float32 upgrade lives here rather than in SessionStore's
    `PRAGMA user_version` chain for the same reason: this table is outside the
    versioned schema, so a version bump would claim to describe a table half
    the databases do not have.

    It runs on every `knn` — the per-turn recall path — so the common case (the
    table exists and is converted) is one PRAGMA; `executescript`, which also
    commits any transaction the caller has open, runs only when needed."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(embeddings_blob)").fetchall()}
    if "vec_blob" in cols and "vec_json" not in cols:
        return
    conn.executescript(_SCHEMA_BLOB_SQL)
    _migrate_json_vectors(conn)


def _migrate_json_vectors(conn: sqlite3.Connection) -> None:
    """Convert a pre-M263a `vec_json` table to packed `vec_blob`, in batches.

    This is the one migration in the project that can take real time on a real
    database, so it reports progress instead of stalling an open silently. It
    is also the only one that drops a column — done last, and only once every
    row has been converted, so an interrupted run resumes instead of losing
    vectors."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(embeddings_blob)").fetchall()}
    if "vec_json" not in cols:
        return
    if "vec_blob" not in cols:
        conn.execute("ALTER TABLE embeddings_blob ADD COLUMN vec_blob BLOB")

    remaining = conn.execute(
        "SELECT COUNT(*) FROM embeddings_blob WHERE vec_blob IS NULL"
    ).fetchone()[0]
    if remaining:
        logger.warning(
            "converting %d embedding vector(s) from JSON to float32 (one-off, M263a)", remaining
        )
        import json as _json

        done = 0
        while True:
            rows = conn.execute(
                "SELECT id, vec_json FROM embeddings_blob WHERE vec_blob IS NULL LIMIT ?",
                (_MIGRATE_BATCH,),
            ).fetchall()
            if not rows:
                break
            with conn:
                conn.executemany(
                    "UPDATE embeddings_blob SET vec_blob = ? WHERE id = ?",
                    [(pack(_json.loads(r[1])), r[0]) for r in rows],
                )
            done += len(rows)
            logger.warning("  %d/%d vectors converted", done, remaining)

    # Rebuild without the old column. `DROP COLUMN` is refused while a NOT NULL
    # column has no default, which `vec_json` is on pre-M263a databases, so the
    # table is recreated instead of patched.
    with conn:
        conn.execute("ALTER TABLE embeddings_blob RENAME TO embeddings_blob_old")
        conn.executescript(_SCHEMA_BLOB_SQL)
        conn.execute(
            "INSERT INTO embeddings_blob(id, ref_kind, ref_id, dim, vec_blob, created_at)"
            " SELECT id, ref_kind, ref_id, dim, vec_blob, created_at"
            "   FROM embeddings_blob_old WHERE vec_blob IS NOT NULL"
        )
        conn.execute("DROP TABLE embeddings_blob_old")

    # Dropping the table frees pages but does not shrink the file: measured on
    # the benchmark corpus, a converted 100k-row database reported 1594 MB
    # against 810 MB before, purely as freelist. A storage migration that makes
    # the file twice as large is not a migration anyone asked for, so reclaim
    # it. VACUUM cannot run inside a transaction and rewrites the whole file —
    # acceptable exactly once, on a path that is already slow and already
    # reporting progress.
    if remaining:
        logger.warning("reclaiming freed pages (VACUUM)")
    with contextlib.suppress(sqlite3.OperationalError):
        conn.execute("VACUUM")


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
    payload = pack(vec_list)
    existing = conn.execute(
        "SELECT id FROM embeddings_blob WHERE ref_kind = ? AND ref_id = ?",
        (ref_kind, ref_id),
    ).fetchone()
    if existing is None:
        cur = conn.execute(
            "INSERT INTO embeddings_blob(ref_kind, ref_id, dim, vec_blob, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (ref_kind, ref_id, dim, payload, wall),
        )
        return int(cur.lastrowid or 0)
    row_id = int(existing["id"])
    conn.execute(
        "UPDATE embeddings_blob SET dim = ?, vec_blob = ?, created_at = ? WHERE id = ?",
        (dim, payload, wall, row_id),
    )
    return row_id


def get_embedding(conn: sqlite3.Connection, *, ref_kind: str, ref_id: int) -> list[float] | None:
    ensure_embeddings_table(conn)
    row = conn.execute(
        "SELECT vec_blob FROM embeddings_blob WHERE ref_kind = ? AND ref_id = ?",
        (ref_kind, ref_id),
    ).fetchone()
    if row is None:
        return None
    return unpack(row["vec_blob"])


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

    dim = len(query)
    # Filter by width in SQL: a row of another dimension cannot match, and
    # fetching it only to drop it in Python is the whole corpus moving for
    # nothing. `dim` is stored, so the database can answer this.
    rows = conn.execute(
        "SELECT ref_kind, ref_id, vec_blob FROM embeddings_blob WHERE dim = ?"
        + (" AND ref_kind = ?" if ref_kind else ""),
        (dim, ref_kind) if ref_kind else (dim,),
    ).fetchall()
    if not rows:
        return []
    refs: list[tuple[str, int]] = []
    blobs: list[bytes] = []
    for row in rows:
        blob = row["vec_blob"]
        if len(blob) != dim * 4:
            continue
        refs.append((row["ref_kind"], int(row["ref_id"])))
        blobs.append(blob)
    if not blobs:
        return []
    # One buffer, one reshape: no per-row Python object is built for the
    # vectors at all, which is the point of the packed format.
    mat = np.frombuffer(b"".join(blobs), dtype="<f4").reshape(len(blobs), dim)
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
    dim = len(query)
    rows = conn.execute(
        "SELECT ref_kind, ref_id, vec_blob FROM embeddings_blob WHERE dim = ?"
        + (" AND ref_kind = ?" if ref_kind else ""),
        (dim, ref_kind) if ref_kind else (dim,),
    ).fetchall()
    if not rows:
        return []
    hits: list[EmbeddingHit] = []
    for row in rows:
        if len(row["vec_blob"]) != dim * 4:
            continue
        cand = unpack(row["vec_blob"])
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


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity in [-1, 1], stabilised with `math.fsum`. Empty,
    length-mismatched or zero-norm inputs → 0.0 (no signal)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = math.fsum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(math.fsum(x * x for x in a))
    nb = math.sqrt(math.fsum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _cosine_distance(a: list[float], b: list[float]) -> float:
    """1 - cosine similarity; a length mismatch is the maximum distance."""
    if len(a) != len(b):
        return 2.0
    return 1.0 - cosine_similarity(a, b)


__all__ = [
    "EmbeddingHit",
    "available_backend",
    "cosine_similarity",
    "ensure_embeddings_table",
    "get_embedding",
    "knn",
    "pack",
    "unpack",
    "upsert_embedding",
]
