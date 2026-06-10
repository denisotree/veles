"""M78 — generic OpenAI-compatible adapter (vLLM, LM Studio, custom servers)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from veles.adapters.local.openai_compatible import OpenAICompatibleProvider
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
        self.base_url = "http://custom/v1"


def test_missing_base_url_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """No default URL ⇒ must be supplied explicitly or via env, else fail fast."""
    monkeypatch.delenv("OPENAI_COMPAT_BASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="base_url"):
        OpenAICompatibleProvider()


def test_explicit_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_COMPAT_BASE_URL", raising=False)
    fake_openai = MagicMock(return_value=MagicMock())
    with patch("veles.adapters.local._base.OpenAI", fake_openai):
        OpenAICompatibleProvider(base_url="http://gpu.lan:8000/v1")
    assert fake_openai.call_args.kwargs["base_url"] == "http://gpu.lan:8000/v1"


def test_env_var_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_COMPAT_BASE_URL", "http://env-fallback/v1")
    fake_openai = MagicMock(return_value=MagicMock())
    with patch("veles.adapters.local._base.OpenAI", fake_openai):
        OpenAICompatibleProvider()
    assert fake_openai.call_args.kwargs["base_url"] == "http://env-fallback/v1"


def test_explicit_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_COMPAT_BASE_URL", "http://env/v1")
    fake_openai = MagicMock(return_value=MagicMock())
    with patch("veles.adapters.local._base.OpenAI", fake_openai):
        OpenAICompatibleProvider(base_url="http://explicit/v1")
    assert fake_openai.call_args.kwargs["base_url"] == "http://explicit/v1"


def test_client_injection_bypasses_url_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests can inject a stub client and skip the base_url enforcement."""
    monkeypatch.delenv("OPENAI_COMPAT_BASE_URL", raising=False)
    p = OpenAICompatibleProvider(client=_StubClient())
    assert p.name == "openai-compat"
    assert p.supports_tools is False


def test_enable_tools_with_injected_client() -> None:
    p = OpenAICompatibleProvider(client=_StubClient(), enable_tools=True)
    assert p.supports_tools is True


def test_create_message_works_through_generic() -> None:
    completion = _Completion(
        choices=[_Choice(message=_AssistantMessage(content="hello"), finish_reason="stop")],
        usage=_Usage(prompt_tokens=3, completion_tokens=2, total_tokens=5),
    )
    p = OpenAICompatibleProvider(client=_StubClient([completion]))
    resp = p.create_message([Message(role="user", content="hi")], model="custom-model")
    assert resp.text == "hello"
    assert resp.usage.total_tokens == 5
