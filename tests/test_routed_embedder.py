"""M326: a local embedder other than Ollama — and knowing whose vectors are stored.

The report: everything ran on llama.cpp, so semantic recall was never on — the only
local embedder Veles knew was Ollama. Now `[routing.tasks].embedding` can name any
OpenAI-wire provider (llama-server serves `/v1/embeddings` with `--embeddings`), and
one that needs no key is local. With two local backends, switching is real, and two
embedders of one width produce vectors that compare as noise.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from veles.core.context import reset_active_project, set_active_project
from veles.core.memory import SessionStore
from veles.core.memory.insight_embeddings import backfill_insight_embeddings
from veles.core.memory.vector import get_embedding, stored_embedder
from veles.core.project import init_project
from veles.core.project_config import save_project_config
from veles.modules.embedding import (
    get_local_embedding_adapter,
    register_embedding_adapter,
    reset_embedding_adapter,
)
from veles.modules.embedding_autodetect import autodetect_embedding_adapter


@pytest.fixture()
def project_with_route(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    reset_embedding_adapter()
    tokens: list = []

    def _make(spec: str):
        project = init_project(tmp_path / "p", name="p")
        save_project_config(project, {"routing": {"tasks": {"embedding": spec}}})
        tokens.append(set_active_project(project))
        return project

    yield _make
    for tok in reversed(tokens):
        reset_active_project(tok)
    reset_embedding_adapter()


def test_a_routed_llamacpp_embedder_is_local(project_with_route, monkeypatch) -> None:
    monkeypatch.setenv("LLAMACPP_BASE_URL", "http://127.0.0.1:8081/v1")
    project_with_route("llamacpp:nomic-embed-text-v1.5")
    adapter = autodetect_embedding_adapter(force=True)
    assert adapter is not None
    assert adapter.name == "llamacpp:nomic-embed-text-v1.5"
    assert getattr(adapter, "base_url", None) == "http://127.0.0.1:8081/v1"
    assert get_local_embedding_adapter() is adapter  # passes the on-device gate


def test_a_cloud_route_does_not_displace_a_local_embedder(project_with_route, monkeypatch) -> None:
    """`[routing.tasks].embedding` set to a cloud model (for `skill dedup`) must not
    take over from a running Ollama: `project_tree` embeds the prompt through the
    ungated adapter, so that would send every prompt to the cloud."""
    import veles.modules.embedding_autodetect as auto

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(auto, "probe_ollama", lambda: True)
    project_with_route("openai:text-embedding-3-small")
    adapter = autodetect_embedding_adapter(force=True)
    assert adapter is not None and adapter.name.startswith("ollama:")


def test_doctor_reads_the_projects_route(project_with_route, monkeypatch) -> None:
    """`veles doctor` used to run this check outside the project, so a routed
    embedder showed as "only a cloud embedder" whenever an API key was set."""
    from veles.core.context import reset_active_project, set_active_project
    from veles.core.doctor import _check_embedding_backend

    monkeypatch.setenv("LLAMACPP_BASE_URL", "http://127.0.0.1:8081/v1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    project = project_with_route("llamacpp:nomic-embed-text-v1.5")
    token = set_active_project(None)  # doctor's own context: no active project
    try:
        result = _check_embedding_backend(project)
    finally:
        reset_active_project(token)
    assert result.status == "ok"
    assert result.details["adapter"] == "llamacpp:nomic-embed-text-v1.5"


# ---- whose vectors are stored ----


class _Embedder:
    is_local = True
    dim = 2

    def __init__(self, name: str) -> None:
        self.name = name

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


def _insight(store: SessionStore) -> int:
    cur = store._conn.execute(
        "INSERT INTO insights(title, body, category, created_at) VALUES (?, ?, ?, ?)",
        ("deploy", "run terraform apply", "curated-session", time.time()),
    )
    store._conn.commit()
    return int(cur.lastrowid or 0)


def test_switching_embedders_starts_the_vectors_over(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "m.db")
    try:
        iid = _insight(store)
        assert backfill_insight_embeddings(store._conn, _Embedder("ollama:nomic")) == 1
        assert stored_embedder(store._conn) == "ollama:nomic"
        # The same embedder again: nothing to redo.
        assert backfill_insight_embeddings(store._conn, _Embedder("ollama:nomic")) == 0
        # Another one: the old vectors go and are redone.
        assert backfill_insight_embeddings(store._conn, _Embedder("llamacpp:bge")) == 1
        assert stored_embedder(store._conn) == "llamacpp:bge"
        assert get_embedding(store._conn, ref_kind="insight", ref_id=iid) is not None
    finally:
        store.close()


def test_recall_ignores_another_embedders_vectors(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "m.db")
    try:
        _insight(store)
        backfill_insight_embeddings(store._conn, _Embedder("ollama:nomic"))
        register_embedding_adapter(_Embedder("llamacpp:bge"))
        assert store.knn_insights([1.0, 0.0], limit=5) == []  # until backfill redoes them
        register_embedding_adapter(_Embedder("ollama:nomic"))
        assert len(store.knn_insights([1.0, 0.0], limit=5)) == 1
    finally:
        reset_embedding_adapter()
        store.close()


def test_vectors_from_before_the_marker_are_redone(tmp_path: Path) -> None:
    """A database embedded before M326 recorded no embedder. Adopting its vectors
    under whatever embedder came next would keep Ollama's vectors under a
    llama.cpp name for good (backfill only fills missing rows) — so they are
    embedded once more instead."""
    from veles.core.memory.vector import upsert_embedding

    store = SessionStore(tmp_path / "m.db")
    try:
        iid = _insight(store)
        upsert_embedding(store._conn, ref_kind="insight", ref_id=iid, vec=[0.5] * 768)
        store._conn.commit()
        register_embedding_adapter(_Embedder("llamacpp:bge"))
        assert store.knn_insights([1.0, 0.0], limit=5) == []  # unknown origin: not used
        assert backfill_insight_embeddings(store._conn, _Embedder("llamacpp:bge")) == 1
        assert stored_embedder(store._conn) == "llamacpp:bge"
        assert len(store.knn_insights([1.0, 0.0], limit=5)) == 1
    finally:
        reset_embedding_adapter()
        store.close()
