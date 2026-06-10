"""Generic `_OpenAICompatibleBase.list_models()` — covers llamacpp +
openai-compat (both inherit straight from the base; ollama overrides with
its native `/api/tags` endpoint and is covered in
`test_local_ollama_adapter.py`)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest

from veles.adapters.local.llamacpp import LlamaCppProvider
from veles.adapters.local.openai_compatible import OpenAICompatibleProvider


@dataclass
class _Model:
    id: str


class _StubClient:
    """Minimal stand-in for `openai.OpenAI` exposing only what the base
    `list_models` touches."""

    def __init__(self, model_ids: list[str]) -> None:
        self.models = MagicMock()
        self.models.list = MagicMock(return_value=[_Model(id=i) for i in model_ids])
        self.base_url = "http://localhost:8080/v1"


def test_llamacpp_list_models_returns_ids() -> None:
    client = _StubClient(["default", "llama-3.2-3b-instruct"])
    p = LlamaCppProvider(client=client)
    assert p.list_models() == ["default", "llama-3.2-3b-instruct"]


def test_openai_compat_list_models_returns_ids() -> None:
    client = _StubClient(["qwen2.5-coder", "mistral-nemo"])
    p = OpenAICompatibleProvider(client=client)
    assert p.list_models() == ["qwen2.5-coder", "mistral-nemo"]


def test_list_models_propagates_errors() -> None:
    """Network/HTTP errors bubble up — the fetcher layer decides fallback."""

    class _BrokenClient:
        def __init__(self) -> None:
            self.models = MagicMock()
            self.models.list = MagicMock(side_effect=RuntimeError("connection refused"))
            self.base_url = "http://localhost:8080/v1"

    p = LlamaCppProvider(client=_BrokenClient())
    with pytest.raises(RuntimeError, match="connection refused"):
        p.list_models()


def test_list_models_empty_page() -> None:
    p = LlamaCppProvider(client=_StubClient([]))
    assert p.list_models() == []


def test_iteration_friendly_page() -> None:
    """openai SDK returns a SyncPage iterable; ensure we iterate, not index."""

    class _IterablePage:
        def __init__(self, items: list[_Model]) -> None:
            self._items = items

        def __iter__(self) -> Any:
            return iter(self._items)

    class _Client:
        def __init__(self) -> None:
            self.models = MagicMock()
            self.models.list = MagicMock(return_value=_IterablePage([_Model(id="a"), _Model(id="b")]))
            self.base_url = "http://localhost:8080/v1"

    p = LlamaCppProvider(client=_Client())
    assert p.list_models() == ["a", "b"]
