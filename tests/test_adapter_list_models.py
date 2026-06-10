"""Cloud-adapter `list_models()` — openrouter, openai-direct, gemini.

Anthropic / claude-cli / gemini-cli deliberately do **not** expose
`list_models()` — the fetcher layer (`tui.screens._model_fetcher`) is
responsible for falling back to a curated list for them; that branch is
covered in `tests/test_model_fetcher.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest


@dataclass
class _Model:
    id: str


def _fake_openai_client(model_ids: list[str]) -> MagicMock:
    client = MagicMock()
    client.models = MagicMock()
    client.models.list = MagicMock(return_value=[_Model(id=i) for i in model_ids])
    return client


# ---------- openrouter ----------


def test_openrouter_list_models_returns_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    from veles.adapters import openrouter as mod

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    fake = _fake_openai_client(["anthropic/claude-opus-4.7", "openai/gpt-4o"])
    with patch.object(mod, "OpenAI", return_value=fake):
        p = mod.OpenRouterProvider()
    assert p.list_models() == ["anthropic/claude-opus-4.7", "openai/gpt-4o"]


def test_openrouter_list_models_propagates_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    from veles.adapters import openrouter as mod

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    broken = MagicMock()
    broken.models = MagicMock()
    broken.models.list = MagicMock(side_effect=RuntimeError("upstream 503"))
    with patch.object(mod, "OpenAI", return_value=broken):
        p = mod.OpenRouterProvider()
    with pytest.raises(RuntimeError, match="upstream 503"):
        p.list_models()


# ---------- openai-direct ----------


def test_openai_direct_list_models_returns_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    from veles.adapters import openai_direct as mod

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    fake = _fake_openai_client(["gpt-4o", "o3", "gpt-4o-mini"])
    with patch.object(mod, "OpenAI", return_value=fake):
        p = mod.OpenAIProvider()
    assert p.list_models() == ["gpt-4o", "o3", "gpt-4o-mini"]


def test_openai_direct_list_models_via_client_kwarg() -> None:
    """Construction via `client=` bypasses env-key check — useful for tests."""
    from veles.adapters.openai_direct import OpenAIProvider

    fake = _fake_openai_client(["gpt-4o-mini"])
    p = OpenAIProvider(client=fake)
    assert p.list_models() == ["gpt-4o-mini"]


# ---------- gemini ----------


@dataclass
class _GeminiModel:
    name: str


class _StubGeminiModels:
    def __init__(self, items: list[_GeminiModel]) -> None:
        self._items = items

    def list(self):  # noqa: A003 (matches SDK shape)
        return iter(self._items)


class _StubGeminiClient:
    def __init__(self, items: list[_GeminiModel]) -> None:
        self.models = _StubGeminiModels(items)


def test_gemini_list_models_strips_models_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    from veles.adapters import gemini as mod

    monkeypatch.setenv("GEMINI_API_KEY", "k")
    stub = _StubGeminiClient(
        [
            _GeminiModel(name="models/gemini-2.5-pro"),
            _GeminiModel(name="models/gemini-2.5-flash"),
            _GeminiModel(name="models/embedding-001"),
        ]
    )
    with patch.object(mod.genai, "Client", return_value=stub):
        p = mod.GeminiProvider()
    assert p.list_models() == ["gemini-2.5-pro", "gemini-2.5-flash", "embedding-001"]


def test_gemini_list_models_skips_empty_names(monkeypatch: pytest.MonkeyPatch) -> None:
    from veles.adapters import gemini as mod

    monkeypatch.setenv("GEMINI_API_KEY", "k")
    stub = _StubGeminiClient(
        [_GeminiModel(name="models/gemini-2.5-pro"), _GeminiModel(name="")]
    )
    with patch.object(mod.genai, "Client", return_value=stub):
        p = mod.GeminiProvider()
    assert p.list_models() == ["gemini-2.5-pro"]


def test_gemini_list_models_passes_unprefixed_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """Defensive: if the SDK ever drops the `models/` prefix, take name as-is."""
    from veles.adapters import gemini as mod

    monkeypatch.setenv("GEMINI_API_KEY", "k")
    stub = _StubGeminiClient([_GeminiModel(name="gemini-3.0")])
    with patch.object(mod.genai, "Client", return_value=stub):
        p = mod.GeminiProvider()
    assert p.list_models() == ["gemini-3.0"]
