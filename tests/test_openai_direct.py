"""M42 — direct OpenAI adapter (api.openai.com via openai SDK)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from veles.adapters.openai_direct import OpenAIProvider, _to_openai_message
from veles.core.provider import Message, ToolCall

# ---------- mock OpenAI client ----------


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
    tool_calls: list[Any] = None  # type: ignore[assignment]


@dataclass
class _ToolFunction:
    name: str
    arguments: str


@dataclass
class _ToolCall:
    id: str
    function: _ToolFunction


class _StubChat:
    def __init__(self, completions: list[Any]) -> None:
        self.completions = list(completions)
        self.last_kwargs: dict[str, Any] | None = None

    def create(self, **kwargs: Any) -> Any:
        self.last_kwargs = kwargs
        if not self.completions:
            raise RuntimeError("no canned response prepared")
        result = self.completions.pop(0)
        return result


class _StubClient:
    def __init__(self, completions: list[Any]) -> None:
        self.chat = _SimpleNamespace(completions=_StubChat(completions))


class _SimpleNamespace:
    def __init__(self, **kw: Any) -> None:
        self.__dict__.update(kw)


# ---------- env-var enforcement ----------


def test_init_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from veles.core import secrets as _secrets

    monkeypatch.setattr(_secrets, "get_provider_key", lambda *_a, **_kw: None)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAIProvider()


def test_init_with_explicit_client_skips_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    OpenAIProvider(client=_StubClient([]))


# ---------- create_message ----------


def test_create_message_returns_text(monkeypatch: pytest.MonkeyPatch) -> None:
    completion = _Completion(
        choices=[
            _Choice(
                message=_AssistantMessage(content="hello", tool_calls=None), finish_reason="stop"
            )
        ],
        usage=_Usage(prompt_tokens=5, completion_tokens=3, total_tokens=8),
    )
    client = _StubClient([completion])
    provider = OpenAIProvider(client=client)
    response = provider.create_message([Message(role="user", content="hi")], model="gpt-4o-mini")
    assert response.text == "hello"
    assert response.tool_calls == []
    assert response.usage.total_tokens == 8


def test_create_message_returns_tool_calls() -> None:
    completion = _Completion(
        choices=[
            _Choice(
                message=_AssistantMessage(
                    content=None,
                    tool_calls=[
                        _ToolCall(
                            id="c1",
                            function=_ToolFunction(name="echo", arguments='{"text": "hi"}'),
                        )
                    ],
                ),
                finish_reason="tool_calls",
            )
        ],
        usage=None,
    )
    client = _StubClient([completion])
    provider = OpenAIProvider(client=client)
    response = provider.create_message(
        [Message(role="user", content="please echo")],
        tools=[{"type": "function", "function": {"name": "echo", "parameters": {}}}],
        model="gpt-4o-mini",
    )
    assert response.text is None
    assert len(response.tool_calls) == 1
    tc = response.tool_calls[0]
    assert tc.id == "c1"
    assert tc.name == "echo"
    assert tc.arguments == {"text": "hi"}


def test_create_message_recovers_from_malformed_tool_args() -> None:
    completion = _Completion(
        choices=[
            _Choice(
                message=_AssistantMessage(
                    content=None,
                    tool_calls=[
                        _ToolCall(
                            id="c1",
                            function=_ToolFunction(name="echo", arguments="{not json"),
                        )
                    ],
                ),
                finish_reason="tool_calls",
            )
        ],
        usage=None,
    )
    provider = OpenAIProvider(client=_StubClient([completion]))
    response = provider.create_message([Message(role="user", content="x")], model="gpt-4o-mini")
    assert response.tool_calls[0].arguments == {"_raw": "{not json"}


# ---------- _to_openai_message ----------


def test_to_openai_message_user() -> None:
    out = _to_openai_message(Message(role="user", content="hi"))
    assert out == {"role": "user", "content": "hi"}


def test_to_openai_message_assistant_with_tool_calls() -> None:
    msg = Message(
        role="assistant",
        content=None,
        tool_calls=[ToolCall(id="x", name="echo", arguments={"text": "y"})],
    )
    out = _to_openai_message(msg)
    assert out["role"] == "assistant"
    assert out["tool_calls"][0]["function"]["name"] == "echo"
    assert out["tool_calls"][0]["function"]["arguments"] == '{"text": "y"}'


def test_to_openai_message_tool_requires_id() -> None:
    with pytest.raises(ValueError, match="tool_call_id"):
        _to_openai_message(Message(role="tool", content="result"))


def test_to_openai_message_tool() -> None:
    out = _to_openai_message(Message(role="tool", content="result", tool_call_id="x"))
    assert out == {"role": "tool", "tool_call_id": "x", "content": "result"}
