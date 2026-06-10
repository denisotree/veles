"""Unit tests for streaming: TextDelta/StreamEnd, default fallback, agent callback."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest

from veles.core.agent import Agent
from veles.core.provider import (
    Message,
    ProviderResponse,
    StreamEnd,
    StreamEvent,
    TextDelta,
    TokenUsage,
    ToolCall,
    default_stream_via_create,
)
from veles.core.tools.registry import Registry, ToolEntry

# ---------- dataclass smoke ----------


def test_text_delta_dataclass() -> None:
    t = TextDelta(text="hello")
    assert t.text == "hello"


def test_stream_end_dataclass_carries_response() -> None:
    response = ProviderResponse(text="x", tool_calls=[], usage=TokenUsage())
    end = StreamEnd(response=response)
    assert end.response is response


# ---------- default fallback ----------


@dataclass
class _SyncStubProvider:
    name: str = "sync-stub"
    supports_tools: bool = True
    supports_streaming: bool = False
    reply: str = "synchronous reply"
    calls: list[Any] = field(default_factory=list)

    def create_message(
        self, messages, tools=None, *, model: str, max_tokens: int = 4096
    ) -> ProviderResponse:
        self.calls.append(model)
        return ProviderResponse(
            text=self.reply,
            tool_calls=[],
            usage=TokenUsage(total_tokens=10),
            finish_reason="stop",
        )

    def stream_message(self, *args, **kwargs) -> Iterator[StreamEvent]:
        yield from default_stream_via_create(self, *args, **kwargs)


def test_default_stream_emits_one_delta_then_end() -> None:
    provider = _SyncStubProvider(reply="hello world")
    events = list(
        provider.stream_message([Message(role="user", content="x")], tools=None, model="m")
    )
    assert len(events) == 2
    assert isinstance(events[0], TextDelta)
    assert events[0].text == "hello world"
    assert isinstance(events[1], StreamEnd)
    assert events[1].response.text == "hello world"


def test_default_stream_skips_delta_when_text_is_none() -> None:
    @dataclass
    class _NoTextProvider:
        name: str = "no-text"
        supports_tools: bool = True
        supports_streaming: bool = False

        def create_message(self, *_args, **_kwargs) -> ProviderResponse:
            return ProviderResponse(
                text=None,
                tool_calls=[ToolCall(id="c", name="x", arguments={})],
                usage=TokenUsage(),
            )

        def stream_message(self, *args, **kwargs):
            yield from default_stream_via_create(self, *args, **kwargs)

    provider = _NoTextProvider()
    events = list(provider.stream_message([Message(role="user", content="x")], model="m"))
    assert len(events) == 1
    assert isinstance(events[0], StreamEnd)


# ---------- agent integration ----------


@dataclass
class _StreamingStubProvider:
    name: str = "stream-stub"
    supports_tools: bool = True
    supports_streaming: bool = True
    text_chunks: list[str] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    create_message_called: bool = False

    def create_message(self, *args, **kwargs) -> ProviderResponse:
        self.create_message_called = True
        return ProviderResponse(text="should-not-be-used", tool_calls=[], usage=TokenUsage())

    def stream_message(self, messages, tools=None, *, model: str, max_tokens: int = 4096):
        text = ""
        for chunk in self.text_chunks:
            yield TextDelta(text=chunk)
            text += chunk
        yield StreamEnd(
            response=ProviderResponse(
                text=text or None,
                tool_calls=list(self.tool_calls),
                usage=TokenUsage(total_tokens=42),
                finish_reason="stop",
            )
        )


def test_agent_run_with_callback_passes_text_chunks_in_order() -> None:
    provider = _StreamingStubProvider(text_chunks=["Hel", "lo, ", "world!"])
    captured: list[str] = []
    agent = Agent(provider=provider, registry=Registry(), model="m", max_iterations=1)
    result = agent.run("hi", on_text_delta=lambda t: captured.append(t))
    assert captured == ["Hel", "lo, ", "world!"]
    assert result.text == "Hello, world!"
    assert result.stopped_reason == "completed"
    assert provider.create_message_called is False


def test_agent_run_without_callback_uses_create_message() -> None:
    provider = _SyncStubProvider(reply="full text")
    agent = Agent(provider=provider, registry=Registry(), model="m", max_iterations=1)
    result = agent.run("hi")
    assert result.text == "full text"
    assert provider.calls == ["m"]


def test_agent_run_streaming_then_tool_call_does_second_turn() -> None:
    """Stream end with tool_calls triggers tool dispatch + a second turn."""

    @dataclass
    class _TwoTurnProvider:
        name: str = "two-turn"
        supports_tools: bool = True
        supports_streaming: bool = True
        turn: int = 0

        def create_message(self, *args, **kwargs):
            raise AssertionError("should use stream_message")

        def stream_message(self, messages, tools=None, *, model, max_tokens=4096):
            self.turn += 1
            if self.turn == 1:
                yield StreamEnd(
                    response=ProviderResponse(
                        text=None,
                        tool_calls=[ToolCall(id="c1", name="noop", arguments={})],
                        usage=TokenUsage(total_tokens=20),
                    )
                )
            else:
                yield TextDelta(text="done")
                yield StreamEnd(
                    response=ProviderResponse(
                        text="done",
                        tool_calls=[],
                        usage=TokenUsage(total_tokens=10),
                    )
                )

    provider = _TwoTurnProvider()
    registry = Registry()
    registry.register(
        ToolEntry(
            name="noop",
            description="noop",
            parameter_schema={"type": "object", "properties": {}},
            handler=lambda **_: "ok",
            is_async=False,
        )
    )
    captured: list[str] = []
    agent = Agent(provider=provider, registry=registry, model="m", max_iterations=5)
    result = agent.run("trigger", on_text_delta=lambda t: captured.append(t))
    assert provider.turn == 2
    assert captured == ["done"]
    assert result.text == "done"


def test_agent_run_streaming_raises_when_no_stream_end() -> None:
    @dataclass
    class _BrokenProvider:
        name: str = "broken"
        supports_tools: bool = True
        supports_streaming: bool = True

        def create_message(self, *_args, **_kwargs):
            raise AssertionError("should not be called")

        def stream_message(self, *_args, **_kwargs):
            yield TextDelta(text="partial")
            # Missing StreamEnd → agent should raise.

    provider = _BrokenProvider()
    agent = Agent(provider=provider, registry=Registry(), model="m", max_iterations=1)
    with pytest.raises(RuntimeError, match="StreamEnd"):
        agent.run("x", on_text_delta=lambda _: None)


# ---------- openrouter streaming with mocked SDK ----------


@dataclass
class _FakeChoice:
    delta: Any
    finish_reason: str | None = None


@dataclass
class _FakeChunk:
    choices: list[_FakeChoice] = field(default_factory=list)
    usage: Any = None


@dataclass
class _FakeDelta:
    content: str | None = None
    tool_calls: list[Any] | None = None


@dataclass
class _FakeUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


def test_openrouter_stream_message_yields_text_deltas(monkeypatch) -> None:
    from veles.adapters import openrouter as orm

    chunks = [
        _FakeChunk(choices=[_FakeChoice(delta=_FakeDelta(content="Hel"))]),
        _FakeChunk(choices=[_FakeChoice(delta=_FakeDelta(content="lo"))]),
        _FakeChunk(
            choices=[_FakeChoice(delta=_FakeDelta(content=None), finish_reason="stop")],
            usage=_FakeUsage(prompt_tokens=5, completion_tokens=2, total_tokens=7),
        ),
    ]

    class _FakeClient:
        def __init__(self):
            self.chat = self
            self.completions = self

        def create(self, **kwargs):
            assert kwargs["stream"] is True
            return iter(chunks)

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    provider = orm.OpenRouterProvider()
    monkeypatch.setattr(provider, "_client", _FakeClient())
    events = list(
        provider.stream_message([Message(role="user", content="hi")], tools=None, model="m")
    )
    deltas = [e for e in events if isinstance(e, TextDelta)]
    ends = [e for e in events if isinstance(e, StreamEnd)]
    assert [d.text for d in deltas] == ["Hel", "lo"]
    assert len(ends) == 1
    assert ends[0].response.text == "Hello"
    assert ends[0].response.usage.total_tokens == 7
    assert ends[0].response.finish_reason == "stop"
