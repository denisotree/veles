"""M192 — embedding-backed recall: backfill + hybrid KNN over insights.

`embeddings_blob` had no production writer (only a test-only migration), so
recall was FTS-keyword-only and paraphrased queries missed. These tests pin the
new pieces: a backfill that embeds insights lacking a vector (run off the hot
path by the dream/curator cycle), and a KNN read that excludes superseded rows.
"""

from __future__ import annotations

import time
from pathlib import Path

from veles.core.memory import SessionStore
from veles.core.memory.insight_embeddings import (
    backfill_insight_embeddings,
    embed_survivor_insights,
)
from veles.core.memory.router import MemoryRouter
from veles.core.memory.vector import get_embedding, upsert_embedding
from veles.core.project import init_project
from veles.modules.embedding import (
    get_local_embedding_adapter,
    register_embedding_adapter,
    reset_embedding_adapter,
)


class _FakeEmbedder:
    """Deterministic, dict-backed embedding adapter for tests."""

    name = "fake"
    dim = 2

    def __init__(
        self, mapping: dict[str, list[float]] | None = None, *, is_local: bool = True
    ) -> None:
        self.mapping = mapping or {}
        self.is_local = is_local
        self.embedded: list[str] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.embedded.extend(texts)
        return [self.mapping.get(t, [0.0, 0.0, 1.0]) for t in texts]


def test_get_local_lazily_autodetects_once(monkeypatch) -> None:
    """B2 (2026-07-07 audit): vector recall must not be inert on REPL turn 1 or
    in a single-shot `veles run` (where the curator — the only place autodetect
    ran — never fires). get_local_embedding_adapter lazily runs autodetect once
    when nothing is registered, then caches, so it self-initialises without a
    separate startup hook and without re-probing on every recall."""
    from veles.modules import embedding as emb

    emb.reset_embedding_adapter()
    calls = {"n": 0}
    fake = _FakeEmbedder({}, is_local=True)

    def fake_autodetect(*, force: bool = False):
        calls["n"] += 1
        emb.register_embedding_adapter(fake)
        return fake

    monkeypatch.setattr(
        "veles.modules.embedding_autodetect.autodetect_embedding_adapter",
        fake_autodetect,
    )
    try:
        got1 = emb.get_local_embedding_adapter()
        got2 = emb.get_local_embedding_adapter()
    finally:
        emb.reset_embedding_adapter()

    assert got1 is fake  # autodetect ran on first call → recall not inert
    assert got2 is fake
    assert calls["n"] == 1  # cached; not re-probed on the hot path every turn


def test_explicit_registration_suppresses_lazy_autodetect(monkeypatch) -> None:
    """A test/host that registers an adapter directly must not have it clobbered
    by a lazy autodetect on first get_local."""
    from veles.modules import embedding as emb

    emb.reset_embedding_adapter()
    preset = _FakeEmbedder({}, is_local=True)
    emb.register_embedding_adapter(preset)

    def boom(*, force: bool = False):
        raise AssertionError("autodetect must not run after explicit registration")

    monkeypatch.setattr(
        "veles.modules.embedding_autodetect.autodetect_embedding_adapter", boom
    )
    try:
        assert emb.get_local_embedding_adapter() is preset
    finally:
        emb.reset_embedding_adapter()


def _insert_insight(store: SessionStore, *, title: str, body: str) -> int:
    cur = store._conn.execute(
        "INSERT INTO insights(title, body, category, created_at) VALUES (?, ?, ?, ?)",
        (title, body, "curated-session", time.time()),
    )
    store._conn.commit()
    return int(cur.lastrowid or 0)


def test_backfill_embeds_insights_without_embeddings(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "m.db")
    try:
        id1 = _insert_insight(store, title="deploy", body="run terraform apply")
        id2 = _insert_insight(store, title="lunch", body="sandwiches at noon")

        n = backfill_insight_embeddings(store, _FakeEmbedder(), limit=10)

        assert n == 2
        assert get_embedding(store._conn, ref_kind="insight", ref_id=id1) is not None
        assert get_embedding(store._conn, ref_kind="insight", ref_id=id2) is not None
    finally:
        store.close()


def test_backfill_is_idempotent(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "m.db")
    try:
        _insert_insight(store, title="deploy", body="run terraform apply")
        backfill_insight_embeddings(store, _FakeEmbedder(), limit=10)

        n2 = backfill_insight_embeddings(store, _FakeEmbedder(), limit=10)

        assert n2 == 0  # already embedded — nothing new to do
    finally:
        store.close()


def test_backfill_skips_superseded_insights(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "m.db")
    try:
        survivor = _insert_insight(store, title="keep", body="canonical fact")
        dropped = _insert_insight(store, title="dup", body="duplicate fact")
        # Mark `dropped` as superseded by `survivor` (dream dedup convention).
        store._conn.execute(
            "INSERT INTO insight_refs(from_insight_id, to_insight_id) VALUES (?, ?)",
            (dropped, survivor),
        )
        store._conn.commit()

        n = backfill_insight_embeddings(store, _FakeEmbedder(), limit=10)

        assert n == 1  # only the survivor is embedded
        assert get_embedding(store._conn, ref_kind="insight", ref_id=survivor) is not None
        assert get_embedding(store._conn, ref_kind="insight", ref_id=dropped) is None
    finally:
        store.close()


def test_knn_insights_returns_nearest_first(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "m.db")
    try:
        a = _insert_insight(store, title="A", body="alpha")
        b = _insert_insight(store, title="B", body="beta")
        upsert_embedding(store._conn, ref_kind="insight", ref_id=a, vec=[1.0, 0.0])
        upsert_embedding(store._conn, ref_kind="insight", ref_id=b, vec=[0.0, 1.0])
        store._conn.commit()

        hits = store.knn_insights([1.0, 0.0], limit=5)

        assert hits[0].id == a  # nearest to the query vector
    finally:
        store.close()


def test_knn_insights_excludes_superseded_even_when_embedded(tmp_path: Path) -> None:
    """A superseded insight that still has an embedding row must not surface —
    vector recall must hide exactly what FTS recall hides."""
    store = SessionStore(tmp_path / "m.db")
    try:
        keep = _insert_insight(store, title="K", body="keep")
        drop = _insert_insight(store, title="D", body="drop")
        upsert_embedding(store._conn, ref_kind="insight", ref_id=keep, vec=[1.0, 0.0])
        upsert_embedding(store._conn, ref_kind="insight", ref_id=drop, vec=[1.0, 0.0])
        store._conn.execute(
            "INSERT INTO insight_refs(from_insight_id, to_insight_id) VALUES (?, ?)",
            (drop, keep),
        )
        store._conn.commit()

        ids = [h.id for h in store.knn_insights([1.0, 0.0], limit=5)]

        assert keep in ids
        assert drop not in ids
    finally:
        store.close()


def _recall_titles(project, store, query: str) -> list[str]:
    return [h.title for h in MemoryRouter(project, store=store).recall(query)]


def test_router_vector_recall_surfaces_paraphrase(tmp_path: Path) -> None:
    """A query sharing NO tokens with the insight (FTS keyword-AND misses) is
    still recalled when a local embedder maps both to the same vector."""
    project = init_project(tmp_path, name="t")
    store = SessionStore(project.memory_db_path)
    iid = _insert_insight(store, title="deploy", body="run terraform apply after migration")
    upsert_embedding(store._conn, ref_kind="insight", ref_id=iid, vec=[1.0, 0.0])
    store._conn.commit()
    query = "shipping infrastructure changes"  # zero token overlap with the insight
    mapping = {"deploy\nrun terraform apply after migration": [1.0, 0.0], query: [1.0, 0.0]}
    register_embedding_adapter(_FakeEmbedder(mapping, is_local=True))
    try:
        assert "deploy" in _recall_titles(project, store, query)
    finally:
        reset_embedding_adapter()
        store.close()


def test_router_dedups_insight_matched_by_both_fts_and_vector(tmp_path: Path) -> None:
    """An insight matched by BOTH FTS (shared tokens) and vector must appear
    once, not twice — the streams no longer overlap after M161 and the vector
    fold must not reintroduce a duplicate."""
    project = init_project(tmp_path, name="t")
    store = SessionStore(project.memory_db_path)
    iid = _insert_insight(store, title="deploy", body="terraform migration steps")
    upsert_embedding(store._conn, ref_kind="insight", ref_id=iid, vec=[1.0, 0.0])
    store._conn.commit()
    query = "terraform migration"  # FTS matches (shared tokens) AND vector matches
    mapping = {"deploy\nterraform migration steps": [1.0, 0.0], query: [1.0, 0.0]}
    register_embedding_adapter(_FakeEmbedder(mapping, is_local=True))
    try:
        titles = _recall_titles(project, store, query)
        assert titles.count("deploy") == 1
    finally:
        reset_embedding_adapter()
        store.close()


def test_router_no_vector_recall_without_local_adapter(tmp_path: Path) -> None:
    """A cloud (non-local) embedder must NOT be sent the query text — vector
    recall is skipped, so a paraphrase (FTS-miss) is not surfaced. This is the
    local-first no-egress guarantee."""
    project = init_project(tmp_path, name="t")
    store = SessionStore(project.memory_db_path)
    iid = _insert_insight(store, title="deploy", body="run terraform apply after migration")
    upsert_embedding(store._conn, ref_kind="insight", ref_id=iid, vec=[1.0, 0.0])
    store._conn.commit()
    query = "shipping infrastructure changes"
    mapping = {"deploy\nrun terraform apply after migration": [1.0, 0.0], query: [1.0, 0.0]}
    register_embedding_adapter(_FakeEmbedder(mapping, is_local=False))
    try:
        assert "deploy" not in _recall_titles(project, store, query)
    finally:
        reset_embedding_adapter()
        store.close()


def test_ollama_adapter_is_local() -> None:
    from veles.modules.embedding_ollama import OllamaEmbeddingAdapter

    assert OllamaEmbeddingAdapter().is_local is True


def test_get_local_embedding_adapter_filters_cloud() -> None:
    register_embedding_adapter(_FakeEmbedder(is_local=False))
    try:
        assert get_local_embedding_adapter() is None  # cloud → filtered out
    finally:
        reset_embedding_adapter()
    register_embedding_adapter(_FakeEmbedder(is_local=True))
    try:
        assert get_local_embedding_adapter() is not None
    finally:
        reset_embedding_adapter()


def test_embed_survivor_insights_uses_local_adapter(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    store = SessionStore(project.memory_db_path)
    iid = _insert_insight(store, title="deploy", body="run terraform apply")
    store.close()
    register_embedding_adapter(_FakeEmbedder(is_local=True))
    try:
        n = embed_survivor_insights(project)
    finally:
        reset_embedding_adapter()
    assert n == 1
    check = SessionStore(project.memory_db_path)
    try:
        assert get_embedding(check._conn, ref_kind="insight", ref_id=iid) is not None
    finally:
        check.close()


def test_embed_survivor_insights_skips_cloud_adapter(tmp_path: Path) -> None:
    """Backfill embeds insight *bodies* — under a cloud adapter that would
    egress project content, it must do nothing (local-first)."""
    project = init_project(tmp_path, name="t")
    store = SessionStore(project.memory_db_path)
    _insert_insight(store, title="deploy", body="run terraform apply")
    store.close()
    register_embedding_adapter(_FakeEmbedder(is_local=False))
    try:
        assert embed_survivor_insights(project) == 0
    finally:
        reset_embedding_adapter()
