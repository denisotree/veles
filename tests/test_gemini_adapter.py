"""M42 — direct Gemini adapter (google-genai SDK)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from veles.adapters.gemini import (
    GeminiProvider,
    _convert_response,
    _convert_tools,
    _split_system_and_contents,
)
from veles.core.provider import Message, ToolCall

# ---------- mock Gemini objects ----------


@dataclass
class _Part:
    text: str | None = None
    function_call: Any = None


@dataclass
class _FunctionCall:
    name: str
    args: dict[str, Any]
    id: str = ""


@dataclass
class _Content:
    parts: list[_Part]


@dataclass
class _Candidate:
    content: _Content
    finish_reason: str | None = None


@dataclass
class _UsageMeta:
    prompt_token_count: int = 0
    candidates_token_count: int = 0
    total_token_count: int = 0


@dataclass
class _GeminiResponse:
    candidates: list[_Candidate]
    usage_metadata: _UsageMeta | None = field(default_factory=_UsageMeta)


class _StubModels:
    def __init__(self, response: Any | None = None, stream_chunks: list[Any] | None = None) -> None:
        self._response = response
        self._stream_chunks = stream_chunks
        self.last_kwargs: dict[str, Any] | None = None

    def generate_content(self, **kwargs: Any) -> Any:
        self.last_kwargs = kwargs
        return self._response

    def generate_content_stream(self, **kwargs: Any) -> Any:
        self.last_kwargs = kwargs
        return iter(self._stream_chunks or [])


class _StubClient:
    def __init__(self, response: Any | None = None, stream_chunks: list[Any] | None = None) -> None:
        self.models = _StubModels(response=response, stream_chunks=stream_chunks)


# ---------- env-var enforcement ----------


def test_init_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    from veles.core import secrets as _secrets

    monkeypatch.setattr(_secrets, "get_provider_key", lambda *_a, **_kw: None)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        GeminiProvider()


def test_init_falls_back_to_google_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "x")
    GeminiProvider()


# ---------- _split_system_and_contents ----------


def test_split_system_collects_into_string() -> None:
    msgs = [
        Message(role="system", content="alpha"),
        Message(role="system", content="beta"),
        Message(role="user", content="hi"),
    ]
    system, contents = _split_system_and_contents(msgs)
    assert system == "alpha\n\nbeta"
    assert contents == [{"role": "user", "parts": [{"text": "hi"}]}]


def test_split_assistant_with_tool_calls() -> None:
    msgs = [
        Message(
            role="assistant",
            content="thinking",
            tool_calls=[ToolCall(id="t1", name="echo", arguments={"x": 1})],
        )
    ]
    _, contents = _split_system_and_contents(msgs)
    assert len(contents) == 1
    assert contents[0]["role"] == "model"
    parts = contents[0]["parts"]
    assert parts[0] == {"text": "thinking"}
    assert parts[1] == {"function_call": {"name": "echo", "args": {"x": 1}}}


def test_split_tool_results_use_assistant_function_name() -> None:
    """Gemini matches tool results by name; lookup must come from the prior tool_call."""
    msgs = [
        Message(
            role="assistant",
            content=None,
            tool_calls=[
                ToolCall(id="t1", name="echo", arguments={}),
            ],
        ),
        Message(role="tool", tool_call_id="t1", content="result"),
    ]
    _, contents = _split_system_and_contents(msgs)
    assert len(contents) == 2
    assert contents[1]["role"] == "user"
    fr = contents[1]["parts"][0]["function_response"]
    assert fr["name"] == "echo"
    assert fr["response"] == {"content": "result"}


def test_split_tool_results_merge_into_one_user_message() -> None:
    msgs = [
        Message(
            role="assistant",
            content=None,
            tool_calls=[
                ToolCall(id="a", name="t_a", arguments={}),
                ToolCall(id="b", name="t_b", arguments={}),
            ],
        ),
        Message(role="tool", tool_call_id="a", content="ra"),
        Message(role="tool", tool_call_id="b", content="rb"),
        Message(role="user", content="next"),
    ]
    _, contents = _split_system_and_contents(msgs)
    # assistant + merged user (function_responses) + new user
    assert len(contents) == 3
    user_responses = contents[1]
    assert user_responses["role"] == "user"
    assert len(user_responses["parts"]) == 2
    assert user_responses["parts"][0]["function_response"]["name"] == "t_a"
    assert user_responses["parts"][1]["function_response"]["name"] == "t_b"


# ---------- tool conversion ----------


def test_convert_tools_translates_openai_shape() -> None:
    out = _convert_tools(
        [
            {
                "type": "function",
                "function": {
                    "name": "search",
                    "description": "Search",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
    )
    assert out == [
        {
            "name": "search",
            "description": "Search",
            "parameters": {"type": "object", "properties": {}},
        }
    ]


# ---------- _convert_response ----------


def test_convert_response_text_only() -> None:
    response = _GeminiResponse(
        candidates=[
            _Candidate(content=_Content(parts=[_Part(text="hello")]), finish_reason="STOP")
        ],
        usage_metadata=_UsageMeta(
            prompt_token_count=10, candidates_token_count=5, total_token_count=15
        ),
    )
    out = _convert_response(response)
    assert out.text == "hello"
    assert out.tool_calls == []
    assert out.usage.total_tokens == 15
    assert out.finish_reason == "STOP"


def test_convert_response_with_function_call() -> None:
    fc = _FunctionCall(name="echo", args={"text": "hi"})
    response = _GeminiResponse(
        candidates=[_Candidate(content=_Content(parts=[_Part(function_call=fc)]))],
    )
    out = _convert_response(response)
    assert len(out.tool_calls) == 1
    assert out.tool_calls[0].name == "echo"
    assert out.tool_calls[0].arguments == {"text": "hi"}


def test_convert_response_total_tokens_fallback_when_unset() -> None:
    response = _GeminiResponse(
        candidates=[_Candidate(content=_Content(parts=[_Part(text="x")]))],
        usage_metadata=_UsageMeta(
            prompt_token_count=4, candidates_token_count=2, total_token_count=0
        ),
    )
    out = _convert_response(response)
    assert out.usage.total_tokens == 6


# ---------- create_message integration ----------


def test_create_message_passes_system_and_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _GeminiResponse(
        candidates=[_Candidate(content=_Content(parts=[_Part(text="ok")]), finish_reason="STOP")],
    )
    client = _StubClient(response=response)
    provider = GeminiProvider(client=client)
    out = provider.create_message(
        [
            Message(role="system", content="be terse"),
            Message(role="user", content="hi"),
        ],
        tools=[{"type": "function", "function": {"name": "noop", "parameters": {}}}],
        model="gemini-2.0-flash",
    )
    assert out.text == "ok"
    last = client.models.last_kwargs
    assert last is not None
    assert last["model"] == "gemini-2.0-flash"
    assert last["config"]["system_instruction"] == "be terse"
    assert last["config"]["tools"][0]["function_declarations"][0]["name"] == "noop"


# ---------- streaming ----------


def test_stream_message_yields_text_chunks_and_function_calls() -> None:
    chunk1 = _GeminiResponse(
        candidates=[_Candidate(content=_Content(parts=[_Part(text="hello ")]))],
        usage_metadata=None,
    )
    chunk2 = _GeminiResponse(
        candidates=[
            _Candidate(
                content=_Content(parts=[_Part(text="world", function_call=None)]),
                finish_reason="STOP",
            )
        ],
        usage_metadata=_UsageMeta(
            prompt_token_count=4, candidates_token_count=2, total_token_count=6
        ),
    )
    provider = GeminiProvider(client=_StubClient(stream_chunks=[chunk1, chunk2]))
    out = list(
        provider.stream_message([Message(role="user", content="x")], model="gemini-2.0-flash")
    )
    text_chunks = [e.text for e in out if hasattr(e, "text")]
    assert text_chunks == ["hello ", "world"]
    end = out[-1]
    assert end.response.text == "hello world"
    assert end.response.usage.total_tokens == 6
    assert end.response.finish_reason == "STOP"
