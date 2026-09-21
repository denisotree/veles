"""M119b: embeddings storage + k-NN.

Tests exercise the pure-Python fallback path explicitly; the numpy
path is smoke-tested only when numpy is importable (skipif decorator).
Backend selection is reset between tests via the private
`_reset_backend_cache` helper so a monkey-patch of importlib doesn't
bleed across.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.memory import SessionStore
from veles.core.memory.vector import (
    EmbeddingHit,
    _reset_backend_cache,
    available_backend,
    delete_embedding,
    ensure_embeddings_table,
    get_embedding,
    knn,
    pack,
    upsert_embedding,
)


@pytest.fixture()
def conn(tmp_path: Path):
    store = SessionStore(tmp_path / "memory.db")
    yield store._conn
    store._conn.close()


@pytest.fixture(autouse=True)
def _reset_backend():
    _reset_backend_cache()
    yield
    _reset_backend_cache()


# ---- backend probe ----


def test_backend_probe_returns_known_value() -> None:
    b = available_backend()
    assert b in {"sqlite-vec", "numpy", "python"}


def test_backend_probe_is_cached() -> None:
    b1 = available_backend()
    b2 = available_backend()
    assert b1 == b2


# ---- schema ----


def test_ensure_table_idempotent(conn) -> None:
    ensure_embeddings_table(conn)
    ensure_embeddings_table(conn)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='embeddings_blob'"
    ).fetchall()
    assert len(rows) == 1


# ---- upsert / get / delete ----


def test_upsert_inserts_new_row(conn) -> None:
    """M263a: storage is float32, so a round-trip is accurate to ~7 significant
    digits rather than exact. That is not a compromise for this data -- the
    embedders themselves emit float32 -- but it is a real change from the JSON
    era, and a test asserting exact equality would have hidden it."""
    rid = upsert_embedding(conn, ref_kind="skill", ref_id=1, vec=[0.1, 0.2, 0.3])
    assert rid > 0
    vec = get_embedding(conn, ref_kind="skill", ref_id=1)
    assert vec is not None
    assert vec == pytest.approx([0.1, 0.2, 0.3], rel=1e-6)


def test_upsert_updates_existing_row(conn) -> None:
    rid1 = upsert_embedding(conn, ref_kind="skill", ref_id=1, vec=[0.1, 0.2])
    rid2 = upsert_embedding(conn, ref_kind="skill", ref_id=1, vec=[0.5, 0.5])
    assert rid1 == rid2
    vec = get_embedding(conn, ref_kind="skill", ref_id=1)
    assert vec == [0.5, 0.5]


def test_upsert_separates_by_ref_kind(conn) -> None:
    upsert_embedding(conn, ref_kind="skill", ref_id=1, vec=[1.0])
    upsert_embedding(conn, ref_kind="tool", ref_id=1, vec=[2.0])
    assert get_embedding(conn, ref_kind="skill", ref_id=1) == [1.0]
    assert get_embedding(conn, ref_kind="tool", ref_id=1) == [2.0]


def test_upsert_empty_vector_rejected(conn) -> None:
    with pytest.raises(ValueError):
        upsert_embedding(conn, ref_kind="skill", ref_id=1, vec=[])


def test_get_missing_returns_none(conn) -> None:
    assert get_embedding(conn, ref_kind="skill", ref_id=99) is None


def test_delete_returns_true_on_hit(conn) -> None:
    upsert_embedding(conn, ref_kind="skill", ref_id=1, vec=[0.1])
    assert delete_embedding(conn, ref_kind="skill", ref_id=1) is True
    assert delete_embedding(conn, ref_kind="skill", ref_id=1) is False


# ---- knn ----


def test_knn_finds_exact_match(conn) -> None:
    upsert_embedding(conn, ref_kind="skill", ref_id=1, vec=[1.0, 0.0])
    upsert_embedding(conn, ref_kind="skill", ref_id=2, vec=[0.0, 1.0])
    hits = knn(conn, [1.0, 0.0], limit=5)
    assert len(hits) == 2
    # ref_id=1 is the exact match → distance ≈ 0
    assert hits[0].ref_id == 1
    assert hits[0].distance == pytest.approx(0.0, abs=1e-6)


def test_knn_orders_by_distance(conn) -> None:
    upsert_embedding(conn, ref_kind="skill", ref_id=1, vec=[1.0, 0.0])
    upsert_embedding(conn, ref_kind="skill", ref_id=2, vec=[0.7, 0.7])
    upsert_embedding(conn, ref_kind="skill", ref_id=3, vec=[0.0, 1.0])
    hits = knn(conn, [1.0, 0.0], limit=3)
    # Closer cosine to (1, 0): id=1 first, id=2 second, id=3 third
    assert [h.ref_id for h in hits] == [1, 2, 3]
    # Distances are monotonic
    assert hits[0].distance <= hits[1].distance <= hits[2].distance


def test_knn_respects_ref_kind_filter(conn) -> None:
    upsert_embedding(conn, ref_kind="skill", ref_id=1, vec=[1.0, 0.0])
    upsert_embedding(conn, ref_kind="tool", ref_id=1, vec=[1.0, 0.0])
    hits = knn(conn, [1.0, 0.0], ref_kind="skill", limit=10)
    assert {h.ref_kind for h in hits} == {"skill"}


def test_knn_empty_table_returns_empty_list(conn) -> None:
    ensure_embeddings_table(conn)
    assert knn(conn, [1.0, 0.0], limit=5) == []


def test_knn_respects_limit(conn) -> None:
    for i in range(10):
        upsert_embedding(conn, ref_kind="skill", ref_id=i, vec=[float(i), 1.0])
    hits = knn(conn, [0.0, 1.0], limit=3)
    assert len(hits) == 3


def test_knn_skips_mismatched_dimensions(conn) -> None:
    """A row with the wrong dimension shouldn't crash the search — it
    gets silently dropped."""
    upsert_embedding(conn, ref_kind="skill", ref_id=1, vec=[1.0, 0.0])
    upsert_embedding(conn, ref_kind="skill", ref_id=2, vec=[1.0, 0.0, 0.0])  # 3-dim
    hits = knn(conn, [1.0, 0.0], limit=5)
    ids = [h.ref_id for h in hits]
    assert 1 in ids
    assert 2 not in ids


def test_knn_returns_typed_hits(conn) -> None:
    upsert_embedding(conn, ref_kind="skill", ref_id=1, vec=[1.0])
    hits = knn(conn, [1.0], limit=5)
    assert isinstance(hits[0], EmbeddingHit)


def test_knn_empty_query_returns_empty(conn) -> None:
    upsert_embedding(conn, ref_kind="skill", ref_id=1, vec=[1.0])
    assert knn(conn, [], limit=5) == []


# ---- backend smoke (skip when not installed) ----


def _has_module(name: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(name) is not None


def test_python_backend_smoke(conn, monkeypatch) -> None:
    """Pin the pure-Python tier explicitly. The generic knn tests above run on
    whatever `available_backend()` picks — once numpy/sqlite-vec are installed
    (dev/CI), that's the accelerated backend, so the python fallback would lose
    coverage. This keeps it deterministically exercised, including the two
    edge cases (mismatched dim skipped, empty query short-circuits)."""
    import veles.core.memory.vector as mv

    monkeypatch.setattr(mv, "_BACKEND", "python")
    upsert_embedding(conn, ref_kind="skill", ref_id=1, vec=[1.0, 0.0])
    upsert_embedding(conn, ref_kind="skill", ref_id=2, vec=[0.7, 0.7])
    upsert_embedding(conn, ref_kind="skill", ref_id=3, vec=[1.0, 0.0, 0.0])  # wrong dim
    hits = mv.knn(conn, [1.0, 0.0], limit=5)
    assert [h.ref_id for h in hits] == [1, 2]  # exact match first; id=3 dim-mismatch dropped
    assert hits[0].distance == pytest.approx(0.0, abs=1e-6)
    assert mv.knn(conn, [], limit=5) == []  # empty query short-circuits before dispatch


@pytest.mark.skipif(not _has_module("numpy"), reason="numpy not installed")
def test_numpy_backend_smoke(conn, monkeypatch) -> None:
    # Force numpy backend even if sqlite-vec is also installed.
    import veles.core.memory.vector as mv

    monkeypatch.setattr(mv, "_BACKEND", "numpy")
    upsert_embedding(conn, ref_kind="skill", ref_id=1, vec=[1.0, 0.0])
    upsert_embedding(conn, ref_kind="skill", ref_id=2, vec=[0.0, 1.0])
    hits = mv.knn(conn, [1.0, 0.0], limit=2)
    assert hits[0].ref_id == 1


# ---- M263a: the JSON -> float32 upgrade ----


def _make_json_table(conn) -> None:
    """Rebuild the pre-M263a shape: vectors stored as JSON text."""
    conn.executescript(
        """
        DROP TABLE IF EXISTS embeddings_blob;
        CREATE TABLE embeddings_blob (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            ref_kind  TEXT NOT NULL,
            ref_id    INTEGER NOT NULL,
            dim       INTEGER NOT NULL,
            vec_json  TEXT NOT NULL,
            created_at REAL NOT NULL,
            UNIQUE (ref_kind, ref_id)
        );
        """
    )


def test_migration_converts_json_vectors(conn) -> None:
    import json

    _make_json_table(conn)
    conn.executemany(
        "INSERT INTO embeddings_blob(ref_kind, ref_id, dim, vec_json, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        [
            ("insight", 1, 3, json.dumps([1.0, 0.0, 0.0]), 1.0),
            ("insight", 2, 3, json.dumps([0.0, 1.0, 0.0]), 2.0),
        ],
    )
    conn.commit()

    ensure_embeddings_table(conn)

    cols = {r[1] for r in conn.execute("PRAGMA table_info(embeddings_blob)").fetchall()}
    assert "vec_blob" in cols
    assert "vec_json" not in cols  # the 3x-larger column does not linger
    assert get_embedding(conn, ref_kind="insight", ref_id=1) == pytest.approx([1.0, 0.0, 0.0])
    assert get_embedding(conn, ref_kind="insight", ref_id=2) == pytest.approx([0.0, 1.0, 0.0])
    # ids survive, because embeddings are referenced by (ref_kind, ref_id) and a
    # renumbering would be invisible until something joined on id.
    ids = [r[0] for r in conn.execute("SELECT id FROM embeddings_blob ORDER BY id").fetchall()]
    assert ids == [1, 2]


def test_migration_is_idempotent(conn) -> None:
    import json

    _make_json_table(conn)
    conn.execute(
        "INSERT INTO embeddings_blob(ref_kind, ref_id, dim, vec_json, created_at)"
        " VALUES ('insight', 1, 2, ?, 1.0)",
        (json.dumps([0.6, 0.8]),),
    )
    conn.commit()

    ensure_embeddings_table(conn)
    ensure_embeddings_table(conn)

    assert get_embedding(conn, ref_kind="insight", ref_id=1) == pytest.approx([0.6, 0.8])
    assert conn.execute("SELECT COUNT(*) FROM embeddings_blob").fetchone()[0] == 1


def test_migration_resumes_after_interruption(conn) -> None:
    """A half-converted table must finish, not lose the unconverted rows: the
    column drop happens only once every row carries a blob."""
    import json

    _make_json_table(conn)
    conn.execute("ALTER TABLE embeddings_blob ADD COLUMN vec_blob BLOB")
    conn.execute(
        "INSERT INTO embeddings_blob(ref_kind, ref_id, dim, vec_json, vec_blob, created_at)"
        " VALUES ('insight', 1, 2, ?, ?, 1.0)",
        (json.dumps([1.0, 0.0]), pack([1.0, 0.0])),
    )
    conn.execute(
        "INSERT INTO embeddings_blob(ref_kind, ref_id, dim, vec_json, created_at)"
        " VALUES ('insight', 2, 2, ?, 2.0)",
        (json.dumps([0.0, 1.0]),),
    )
    conn.commit()

    ensure_embeddings_table(conn)

    assert get_embedding(conn, ref_kind="insight", ref_id=1) == pytest.approx([1.0, 0.0])
    assert get_embedding(conn, ref_kind="insight", ref_id=2) == pytest.approx([0.0, 1.0])


def test_knn_ignores_rows_of_another_width(conn) -> None:
    """Dimension mismatch is filtered in SQL now; a 3-d row must not be scored
    against a 2-d query, and must not break the scan either."""
    upsert_embedding(conn, ref_kind="insight", ref_id=1, vec=[1.0, 0.0])
    upsert_embedding(conn, ref_kind="insight", ref_id=2, vec=[1.0, 0.0, 0.0])
    hits = knn(conn, [1.0, 0.0], ref_kind="insight", limit=5)
    assert [h.ref_id for h in hits] == [1]
