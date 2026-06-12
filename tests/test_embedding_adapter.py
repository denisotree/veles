"""EmbeddingAdapter Protocol + registry + autodetect tests.

Concrete adapters (Ollama, OpenAI) are mocked — the actual provider
calls are out of scope for unit tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.embedding_notice import (
    SETUP_HINT_CATEGORY,
    SETUP_HINT_TITLE,
    maybe_surface_embedding_setup_hint,
)
from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.modules import (
    EmbeddingAdapter,
    EmbeddingError,
    autodetect_embedding_adapter,
    get_embedding_adapter,
    register_embedding_adapter,
    reset_embedding_adapter,
)


@pytest.fixture(autouse=True)
def _isolate_registry():
    reset_embedding_adapter()
    yield
    reset_embedding_adapter()


@pytest.fixture()
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


class _StubEmbedding:
    name = "stub"
    dim = 4

    def __init__(self, *, fixed: list[float] | None = None) -> None:
        self._fixed = fixed or [0.1, 0.2, 0.3, 0.4]
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [list(self._fixed) for _ in texts]


# ---- protocol + registry ----


def test_no_adapter_by_default() -> None:
    assert get_embedding_adapter() is None


def test_register_and_get() -> None:
    a = _StubEmbedding()
    register_embedding_adapter(a)
    assert get_embedding_adapter() is a


def test_register_none_clears() -> None:
    register_embedding_adapter(_StubEmbedding())
    register_embedding_adapter(None)
    assert get_embedding_adapter() is None


def test_protocol_isinstance_works() -> None:
    assert isinstance(_StubEmbedding(), EmbeddingAdapter)


def test_embedding_error_subclass() -> None:
    with pytest.raises(EmbeddingError):
        raise EmbeddingError("model not loaded")


# ---- autodetect ----


def test_autodetect_picks_ollama_when_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When `probe_ollama` returns True, the Ollama adapter wins —
    no env credential check happens."""
    monkeypatch.setattr("veles.modules.embedding_autodetect.probe_ollama", lambda: True)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    adapter = autodetect_embedding_adapter(force=True)
    assert adapter is not None
    assert "ollama:" in adapter.name


def test_autodetect_falls_back_to_openrouter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No Ollama, but OPENROUTER_API_KEY set → OpenAI-shape adapter."""
    monkeypatch.setattr("veles.modules.embedding_autodetect.probe_ollama", lambda: False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    adapter = autodetect_embedding_adapter(force=True)
    assert adapter is not None
    assert "openai:" in adapter.name
    assert "openrouter" in adapter.name


def test_autodetect_falls_back_to_openai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenRouter unset but OPENAI_API_KEY set → direct OpenAI."""
    monkeypatch.setattr("veles.modules.embedding_autodetect.probe_ollama", lambda: False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    adapter = autodetect_embedding_adapter(force=True)
    assert adapter is not None
    assert "openai" in adapter.name
    # Default base_url, no openrouter substring
    assert "openrouter" not in adapter.name


def test_autodetect_returns_none_when_nothing_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No Ollama, no API key → None. Ranking falls back to
    token-based; user sees the setup-hint insight."""
    monkeypatch.setattr("veles.modules.embedding_autodetect.probe_ollama", lambda: False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    adapter = autodetect_embedding_adapter(force=True)
    assert adapter is None
    # Registered None explicitly
    assert get_embedding_adapter() is None


def test_autodetect_caches_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without `force=True`, autodetect returns the cached adapter
    and doesn't re-probe."""
    monkeypatch.setattr("veles.modules.embedding_autodetect.probe_ollama", lambda: True)
    first = autodetect_embedding_adapter(force=True)
    # Simulate Ollama going down — repeat call must still see first
    monkeypatch.setattr("veles.modules.embedding_autodetect.probe_ollama", lambda: False)
    second = autodetect_embedding_adapter()
    assert second is first


# ---- setup-hint notice ----


def test_setup_hint_writes_row(isolated_home: Path, tmp_path: Path) -> None:
    project = init_project(tmp_path / "proj", name="proj")
    fresh = maybe_surface_embedding_setup_hint(project)
    assert fresh is True

    store = SessionStore(project.memory_db_path)
    row = store._conn.execute(
        "SELECT title, body, category FROM insights WHERE category = ?",
        (SETUP_HINT_CATEGORY,),
    ).fetchone()
    store._conn.close()
    assert row is not None
    assert row["title"] == SETUP_HINT_TITLE
    assert "Ollama" in row["body"]
    assert "OPENROUTER_API_KEY" in row["body"]


def test_setup_hint_idempotent(isolated_home: Path, tmp_path: Path) -> None:
    """Calling twice doesn't create a duplicate insight row — the
    notice surfaces once and then quiets down."""
    project = init_project(tmp_path / "proj", name="proj")
    assert maybe_surface_embedding_setup_hint(project) is True
    assert maybe_surface_embedding_setup_hint(project) is False

    store = SessionStore(project.memory_db_path)
    count = store._conn.execute(
        "SELECT COUNT(*) AS n FROM insights WHERE category = ?",
        (SETUP_HINT_CATEGORY,),
    ).fetchone()["n"]
    store._conn.close()
    assert count == 1


def test_setup_hint_no_crash_on_db_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """If the SessionStore raises during open, the notice silently
    no-ops — we don't break the user's turn for a UI suggestion."""
    import sqlite3 as _sqlite3

    from veles.core.project import Project

    def _boom(_path):
        raise _sqlite3.Error("simulated db open failure")

    # Patch the module that `maybe_surface_embedding_setup_hint`
    # imports SessionStore from (lazy import → patch the source).
    monkeypatch.setattr("veles.core.memory.SessionStore", _boom)
    fake = Project(root=tmp_path / "ghost", name="ghost", created_at=0.0)
    # Should not raise
    result = maybe_surface_embedding_setup_hint(fake)
    assert result is False


# ---- ollama adapter unit (mocked HTTP) ----


def test_ollama_adapter_constructs_with_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from veles.modules.embedding_ollama import OllamaEmbeddingAdapter

    monkeypatch.delenv("VELES_OLLAMA_EMBED_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    a = OllamaEmbeddingAdapter()
    assert a.model == "nomic-embed-text"
    assert a.host == "http://localhost:11434"
    assert a.dim == 768
    assert a.name == "ollama:nomic-embed-text"


def test_ollama_adapter_respects_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from veles.modules.embedding_ollama import OllamaEmbeddingAdapter

    monkeypatch.setenv("VELES_OLLAMA_EMBED_MODEL", "mxbai-embed-large")
    monkeypatch.setenv("OLLAMA_HOST", "http://remote.example:9999")
    a = OllamaEmbeddingAdapter()
    assert a.model == "mxbai-embed-large"
    assert a.host == "http://remote.example:9999"


def test_ollama_adapter_embeds_via_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mock urlopen → adapter returns the parsed vector."""
    import json

    from veles.modules.embedding_ollama import OllamaEmbeddingAdapter

    class _Resp:
        def __init__(self, body: bytes) -> None:
            self._body = body

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def read(self) -> bytes:
            return self._body

    def fake_urlopen(req, timeout=None):
        return _Resp(json.dumps({"embedding": [1.0, 2.0, 3.0]}).encode())

    monkeypatch.setattr("veles.modules.embedding_ollama.urllib.request.urlopen", fake_urlopen)
    a = OllamaEmbeddingAdapter()
    vecs = a.embed(["hello"])
    assert vecs == [[1.0, 2.0, 3.0]]
    # dim auto-updated from response shape
    assert a.dim == 3


def test_ollama_adapter_raises_embedding_error_on_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import urllib.error

    from veles.modules.embedding_ollama import OllamaEmbeddingAdapter

    def boom(req, timeout=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("veles.modules.embedding_ollama.urllib.request.urlopen", boom)
    with pytest.raises(EmbeddingError) as ei:
        OllamaEmbeddingAdapter().embed(["x"])
    assert "ollama" in str(ei.value).lower()


def test_ollama_adapter_empty_input_returns_empty() -> None:
    from veles.modules.embedding_ollama import OllamaEmbeddingAdapter

    assert OllamaEmbeddingAdapter().embed([]) == []


# ---- openai wrapper ----


def test_openai_wrapper_build_from_env_picks_openrouter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from veles.modules.embedding_openai import build_from_env

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
    a = build_from_env()
    assert a is not None
    # OpenRouter takes priority
    assert "openrouter" in a.name


def test_openai_wrapper_build_from_env_falls_back_to_openai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from veles.modules.embedding_openai import build_from_env

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
    a = build_from_env()
    assert a is not None
    assert "openai:" in a.name


def test_openai_wrapper_build_from_env_returns_none_without_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from veles.modules.embedding_openai import build_from_env

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert build_from_env() is None
