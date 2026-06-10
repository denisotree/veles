"""M78 — llama.cpp adapter (local-model provider via OpenAI-compatible endpoint)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from veles.adapters.local.llamacpp import LlamaCppProvider
from veles.core.provider import Message


@dataclass
class _Choice:
    message: Any
    finish_reason: str | None = None


@dataclass
class _Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class _Completion:
    choices: list[_Choice]
    usage: _Usage | None


@dataclass
class _AssistantMessage:
    content: str | None = None
    tool_calls: list[Any] | None = None


class _SimpleNamespace:
    def __init__(self, **kw: Any) -> None:
        self.__dict__.update(kw)


class _StubChat:
    def __init__(self, results: list[Any]) -> None:
        self._results = list(results)
        self.last_kwargs: dict[str, Any] | None = None

    def create(self, **kwargs: Any) -> Any:
        self.last_kwargs = kwargs
        return self._results.pop(0)


class _StubClient:
    def __init__(self, results: list[Any] | None = None) -> None:
        self.chat = _SimpleNamespace(completions=_StubChat(results or []))
        self.base_url = "http://localhost:8080/v1"


def test_defaults() -> None:
    p = LlamaCppProvider(client=_StubClient())
    assert p.name == "llamacpp"
    assert p.supports_streaming is True
    assert p.supports_tools is False


def test_default_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLAMACPP_BASE_URL", raising=False)
    fake_openai = MagicMock(return_value=MagicMock())
    with patch("veles.adapters.local._base.OpenAI", fake_openai):
        LlamaCppProvider()
    assert fake_openai.call_args.kwargs["base_url"] == "http://localhost:8080/v1"


def test_base_url_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLAMACPP_BASE_URL", "http://10.0.0.5:9000/v1")
    fake_openai = MagicMock(return_value=MagicMock())
    with patch("veles.adapters.local._base.OpenAI", fake_openai):
        LlamaCppProvider()
    assert fake_openai.call_args.kwargs["base_url"] == "http://10.0.0.5:9000/v1"


def test_explicit_base_url_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLAMACPP_BASE_URL", "http://from-env/v1")
    fake_openai = MagicMock(return_value=MagicMock())
    with patch("veles.adapters.local._base.OpenAI", fake_openai):
        LlamaCppProvider(base_url="http://explicit/v1")
    assert fake_openai.call_args.kwargs["base_url"] == "http://explicit/v1"


def test_enable_tools() -> None:
    p = LlamaCppProvider(client=_StubClient(), enable_tools=True)
    assert p.supports_tools is True


def test_create_message_round_trip() -> None:
    completion = _Completion(
        choices=[_Choice(message=_AssistantMessage(content="hi"), finish_reason="stop")],
        usage=_Usage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
    )
    p = LlamaCppProvider(client=_StubClient([completion]))
    # llama-server ignores the model field — caller can pass anything.
    resp = p.create_message([Message(role="user", content="ping")], model="default")
    assert resp.text == "hi"
    assert resp.usage.total_tokens == 2


def test_huge_request_timeout_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Local models can run for minutes — default total timeout is 10 minutes."""
    monkeypatch.delenv("LLAMACPP_BASE_URL", raising=False)
    fake_openai = MagicMock(return_value=MagicMock())
    with patch("veles.adapters.local._base.OpenAI", fake_openai):
        LlamaCppProvider()
    assert fake_openai.call_args.kwargs["timeout"] == 600.0
