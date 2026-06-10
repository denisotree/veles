"""M42 — direct Anthropic adapter (api.anthropic.com via anthropic SDK)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from veles.adapters.anthropic import (
    AnthropicProvider,
    _convert_response,
    _convert_tools,
    _split_system_and_messages,
)
from veles.core.cache_hints import CACHE_BREAKPOINT_SENTINEL, build_anthropic_system_blocks
from veles.core.provider import Message, ToolCall

# ---------- mock Anthropic objects ----------


@dataclass
class _TextBlock:
    text: str
    type: str = "text"


@dataclass
class _ToolUseBlock:
    id: str
    name: str
    input: dict[str, Any]
    type: str = "tool_use"


@dataclass
class _Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class _AnthropicResponse:
    content: list[Any]
    stop_reason: str | None = None
    usage: _Usage | None = field(default_factory=_Usage)


class _StubMessages:
    def __init__(self, response: Any | None = None, stream_events: list[Any] | None = None) -> None:
        self._response = response
        self._stream_events = stream_events
        self.last_kwargs: dict[str, Any] | None = None

    def create(self, **kwargs: Any) -> Any:
        self.last_kwargs = kwargs
        if kwargs.get("stream"):
            return iter(self._stream_events or [])
        return self._response


class _StubClient:
    def __init__(self, response: Any | None = None, stream_events: list[Any] | None = None) -> None:
        self.messages = _StubMessages(response=response, stream_events=stream_events)


# ---------- env-var enforcement ----------


def test_init_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from veles.core import secrets as _secrets

    monkeypatch.setattr(_secrets, "get_provider_key", lambda *_a, **_kw: None)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        AnthropicProvider()


def test_init_with_explicit_client_skips_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    AnthropicProvider(client=_StubClient())


# ---------- message conversion ----------


def test_split_system_collects_into_string() -> None:
    msgs = [
        Message(role="system", content="part one"),
        Message(role="system", content="part two"),
        Message(role="user", content="hi"),
    ]
    system, native = _split_system_and_messages(msgs)
    assert system == "part one\n\npart two"
    assert native == [{"role": "user", "content": "hi"}]


def test_split_assistant_with_tool_calls_emits_blocks() -> None:
    msgs = [
        Message(
            role="assistant",
            content="thinking",
            tool_calls=[ToolCall(id="t1", name="echo", arguments={"text": "x"})],
        )
    ]
    _, native = _split_system_and_messages(msgs)
    assert len(native) == 1
    assert native[0]["role"] == "assistant"
    blocks = native[0]["content"]
    assert blocks[0] == {"type": "text", "text": "thinking"}
    assert blocks[1] == {
        "type": "tool_use",
        "id": "t1",
        "name": "echo",
        "input": {"text": "x"},
    }


def test_split_consecutive_tool_messages_merge_into_one_user() -> None:
    msgs = [
        Message(
            role="assistant",
            content=None,
            tool_calls=[
                ToolCall(id="t1", name="a", arguments={}),
                ToolCall(id="t2", name="b", arguments={}),
            ],
        ),
        Message(role="tool", tool_call_id="t1", content="result1"),
        Message(role="tool", tool_call_id="t2", content="result2"),
        Message(role="user", content="next turn"),
    ]
    _, native = _split_system_and_messages(msgs)
    # assistant + merged tool_results + new user
    assert len(native) == 3
    assert native[0]["role"] == "assistant"
    assert native[1]["role"] == "user"
    blocks = native[1]["content"]
    assert len(blocks) == 2
    assert blocks[0]["tool_use_id"] == "t1"
    assert blocks[0]["content"] == "result1"
    assert blocks[1]["tool_use_id"] == "t2"
    assert native[2] == {"role": "user", "content": "next turn"}


def test_convert_tools_translates_openai_shape() -> None:
    out = _convert_tools(
        [
            {
                "type": "function",
                "function": {
                    "name": "search",
                    "description": "Search the wiki",
                    "parameters": {"type": "object", "properties": {"q": {"type": "string"}}},
                },
            }
        ]
    )
    assert out == [
        {
            "name": "search",
            "description": "Search the wiki",
            "input_schema": {"type": "object", "properties": {"q": {"type": "string"}}},
        }
    ]


def test_convert_tools_handles_flat_shape() -> None:
    """Tolerate already-Anthropic-shaped or unwrapped tool dicts."""
    out = _convert_tools([{"name": "x", "description": "d"}])
    assert out == [
        {
            "name": "x",
            "description": "d",
            "input_schema": {"type": "object", "properties": {}},
        }
    ]


# ---------- _convert_response ----------


def test_convert_response_text_only() -> None:
    response = _AnthropicResponse(
        content=[_TextBlock(text="hello")],
        stop_reason="end_turn",
        usage=_Usage(input_tokens=10, output_tokens=5),
    )
    out = _convert_response(response)
    assert out.text == "hello"
    assert out.tool_calls == []
    assert out.usage.total_tokens == 15
    assert out.finish_reason == "end_turn"


def test_convert_response_with_tool_use() -> None:
    response = _AnthropicResponse(
        content=[
            _TextBlock(text="going to call"),
            _ToolUseBlock(id="t1", name="echo", input={"text": "hi"}),
        ],
        stop_reason="tool_use",
    )
    out = _convert_response(response)
    assert out.text == "going to call"
    assert len(out.tool_calls) == 1
    assert out.tool_calls[0].name == "echo"
    assert out.tool_calls[0].arguments == {"text": "hi"}


def test_convert_response_handles_non_dict_input() -> None:
    """Defensive: malformed input field should land as `_raw`."""
    response = _AnthropicResponse(
        content=[_ToolUseBlock(id="t1", name="x", input="not-a-dict")],  # type: ignore[arg-type]
    )
    out = _convert_response(response)
    assert out.tool_calls[0].arguments == {"_raw": "not-a-dict"}


# ---------- create_message integration ----------


def test_create_message_round_trip() -> None:
    response = _AnthropicResponse(
        content=[_TextBlock(text="hi back")],
        stop_reason="end_turn",
        usage=_Usage(input_tokens=4, output_tokens=2),
    )
    client = _StubClient(response=response)
    provider = AnthropicProvider(client=client)
    out = provider.create_message(
        [
            Message(role="system", content="be terse"),
            Message(role="user", content="hi"),
        ],
        tools=[{"type": "function", "function": {"name": "noop", "parameters": {}}}],
        model="claude-sonnet-4-6",
    )
    assert out.text == "hi back"
    assert client.messages.last_kwargs["system"] == "be terse"
    assert client.messages.last_kwargs["tools"][0]["name"] == "noop"


# ---------- streaming ----------


@dataclass
class _StreamEvent:
    type: str
    delta: Any | None = None
    content_block: Any | None = None
    message: Any | None = None
    usage: Any | None = None


@dataclass
class _Delta:
    type: str | None = None
    text: str | None = None
    partial_json: str | None = None
    stop_reason: str | None = None


def test_stream_message_yields_text_deltas_and_final_response() -> None:
    events = [
        _StreamEvent(
            type="message_start", message=type("M", (), {"usage": _Usage(input_tokens=4)})()
        ),
        _StreamEvent(type="content_block_delta", delta=_Delta(type="text_delta", text="hello ")),
        _StreamEvent(type="content_block_delta", delta=_Delta(type="text_delta", text="world")),
        _StreamEvent(
            type="message_delta",
            delta=_Delta(stop_reason="end_turn"),
            usage=_Usage(output_tokens=3),
        ),
    ]
    client = _StubClient(stream_events=events)
    provider = AnthropicProvider(client=client)
    out = list(
        provider.stream_message([Message(role="user", content="hi")], model="claude-sonnet-4-6")
    )
    text_chunks = [e.text for e in out if hasattr(e, "text")]
    assert text_chunks == ["hello ", "world"]
    end = out[-1]
    assert end.response.text == "hello world"
    assert end.response.finish_reason == "end_turn"
    assert end.response.usage.total_tokens == 4 + 3


def test_stream_message_assembles_tool_call_from_input_json_deltas() -> None:
    events = [
        _StreamEvent(
            type="content_block_start",
            content_block=type("B", (), {"type": "tool_use", "id": "t1", "name": "echo"})(),
        ),
        _StreamEvent(
            type="content_block_delta",
            delta=_Delta(type="input_json_delta", partial_json='{"text":'),
        ),
        _StreamEvent(
            type="content_block_delta", delta=_Delta(type="input_json_delta", partial_json=' "hi"}')
        ),
        _StreamEvent(type="content_block_stop"),
        _StreamEvent(type="message_delta", delta=_Delta(stop_reason="tool_use")),
    ]
    provider = AnthropicProvider(client=_StubClient(stream_events=events))
    out = list(
        provider.stream_message([Message(role="user", content="x")], model="claude-sonnet-4-6")
    )
    end = out[-1]
    assert len(end.response.tool_calls) == 1
    assert end.response.tool_calls[0].arguments == {"text": "hi"}


# ---------- M42b — native cache_control on system prompt ----------


def test_split_system_passes_plain_string_when_no_sentinel() -> None:
    msgs = [
        Message(role="system", content="just regular text"),
        Message(role="user", content="hi"),
    ]
    system, _ = _split_system_and_messages(msgs)
    assert system == "just regular text"


def test_split_system_returns_blocks_with_cache_control_when_sentinel_present() -> None:
    msgs = [
        Message(
            role="system",
            content="STABLE PREFIX" + CACHE_BREAKPOINT_SENTINEL + "dynamic suffix",
        ),
        Message(role="user", content="hi"),
    ]
    system, _ = _split_system_and_messages(msgs)
    assert isinstance(system, list)
    assert system[0]["text"] == "STABLE PREFIX"
    assert system[0]["cache_control"] == {"type": "ephemeral"}
    assert system[1] == {"type": "text", "text": "dynamic suffix"}


def test_split_system_returns_single_cached_block_when_no_suffix() -> None:
    msgs = [
        Message(role="system", content="ONLY STABLE" + CACHE_BREAKPOINT_SENTINEL),
        Message(role="user", content="hi"),
    ]
    system, _ = _split_system_and_messages(msgs)
    assert isinstance(system, list)
    assert len(system) == 1
    assert system[0] == {
        "type": "text",
        "text": "ONLY STABLE",
        "cache_control": {"type": "ephemeral"},
    }


def test_split_system_returns_plain_block_when_no_prefix() -> None:
    """Sentinel at start = no stable prefix to cache; emit the dynamic part as plain block."""
    msgs = [
        Message(role="system", content=CACHE_BREAKPOINT_SENTINEL + "only dynamic"),
        Message(role="user", content="hi"),
    ]
    system, _ = _split_system_and_messages(msgs)
    assert isinstance(system, list)
    assert len(system) == 1
    assert "cache_control" not in system[0]
    assert system[0]["text"] == "only dynamic"


def test_split_system_returns_none_when_only_sentinel() -> None:
    msgs = [
        Message(role="system", content=CACHE_BREAKPOINT_SENTINEL),
        Message(role="user", content="hi"),
    ]
    system, _ = _split_system_and_messages(msgs)
    assert system is None


def test_split_system_joins_multiple_then_caches() -> None:
    """Joined system parts may contain the sentinel from any contributor."""
    msgs = [
        Message(role="system", content="agents md content"),
        Message(role="system", content="index md" + CACHE_BREAKPOINT_SENTINEL + "memory ctx"),
        Message(role="user", content="hi"),
    ]
    system, _ = _split_system_and_messages(msgs)
    assert isinstance(system, list)
    assert system[0]["cache_control"] == {"type": "ephemeral"}
    assert "agents md content" in system[0]["text"]
    assert "index md" in system[0]["text"]
    assert system[1]["text"] == "memory ctx"


def test_create_message_forwards_cache_blocks_to_sdk() -> None:
    """Adapter passes the list-of-blocks `system=` straight through to the SDK."""
    response = _AnthropicResponse(content=[_TextBlock(text="ok")], stop_reason="end_turn")
    client = _StubClient(response=response)
    provider = AnthropicProvider(client=client)
    msgs = [
        Message(role="system", content="STABLE" + CACHE_BREAKPOINT_SENTINEL + "dyn"),
        Message(role="user", content="hi"),
    ]
    provider.create_message(msgs, model="claude-sonnet-4-6")
    kwargs = client.messages.last_kwargs
    assert kwargs is not None
    sent = kwargs["system"]
    assert isinstance(sent, list)
    assert sent[0]["cache_control"] == {"type": "ephemeral"}
    assert sent[0]["text"] == "STABLE"
    assert sent[1]["text"] == "dyn"


def test_create_message_forwards_plain_string_when_no_sentinel() -> None:
    response = _AnthropicResponse(content=[_TextBlock(text="ok")], stop_reason="end_turn")
    client = _StubClient(response=response)
    provider = AnthropicProvider(client=client)
    msgs = [
        Message(role="system", content="just text"),
        Message(role="user", content="hi"),
    ]
    provider.create_message(msgs, model="claude-sonnet-4-6")
    sent = client.messages.last_kwargs["system"]
    assert sent == "just text"


def test_create_message_omits_system_when_none() -> None:
    response = _AnthropicResponse(content=[_TextBlock(text="ok")], stop_reason="end_turn")
    client = _StubClient(response=response)
    provider = AnthropicProvider(client=client)
    provider.create_message([Message(role="user", content="hi")], model="claude-sonnet-4-6")
    assert "system" not in client.messages.last_kwargs


def test_stream_message_forwards_cache_blocks_to_sdk() -> None:
    """Streaming path uses the same conversion — verify cache hints reach the wire."""
    client = _StubClient(stream_events=[])
    provider = AnthropicProvider(client=client)
    msgs = [
        Message(role="system", content="P" + CACHE_BREAKPOINT_SENTINEL + "D"),
        Message(role="user", content="hi"),
    ]
    list(provider.stream_message(msgs, model="claude-sonnet-4-6"))
    sent = client.messages.last_kwargs["system"]
    assert isinstance(sent, list)
    assert sent[0]["cache_control"] == {"type": "ephemeral"}


def test_build_anthropic_system_blocks_none_input() -> None:
    assert build_anthropic_system_blocks(None) is None
    assert build_anthropic_system_blocks("") is None


def test_build_anthropic_system_blocks_no_sentinel_passthrough() -> None:
    assert build_anthropic_system_blocks("plain") == "plain"


def test_build_anthropic_system_blocks_whitespace_only_suffix_drops_block() -> None:
    """A sentinel followed by only whitespace = the suffix is meaningless; one block."""
    out = build_anthropic_system_blocks("STABLE" + CACHE_BREAKPOINT_SENTINEL + "   \n  ")
    assert isinstance(out, list)
    assert len(out) == 1
    assert out[0]["cache_control"] == {"type": "ephemeral"}
