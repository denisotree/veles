"""M133: reasoning/thinking capture.

Reasoning-capable models stream their chain-of-thought on a side channel
(`ReasoningDelta`). The agent forwards it as a typed `ThinkingDelta` event
to the listener (feeding the TUI inspector) and the persistent log — but
NEVER to `on_text_delta`, so the answer shown in chat stays clean. The
OpenAI-compatible wire layer parses the `reasoning` / `reasoning_content`
delta field (OpenRouter + OpenAI-compat backends).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from veles.adapters.openai_direct import OpenAIProvider
from veles.core.agent import Agent
from veles.core.events import ThinkingDelta
from veles.core.provider import (
    Message,
    ProviderResponse,
    ReasoningDelta,
    StreamEnd,
    TextDelta,
    TokenUsage,
)
from veles.core.tools.registry import Registry


def _final(text: str) -> ProviderResponse:
    return ProviderResponse(
        text=text,
        tool_calls=[],
        usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        finish_reason="stop",
    )


@dataclass
class _ReasoningProvider:
    name: str = "stub"
    supports_tools: bool = True
    supports_streaming: bool = True

    def create_message(self, *a, **k):  # noqa: ANN002, ANN003
        raise NotImplementedError

    def stream_message(self, messages, tools=None, *, model, max_tokens=4096):  # noqa: ANN001
        del messages, tools, model, max_tokens
        yield ReasoningDelta(text="let me think… ")
        yield ReasoningDelta(text="2+2 is 4.")
        yield TextDelta(text="The answer is 4.")
        yield StreamEnd(response=_final("The answer is 4."))


def test_agent_forwards_reasoning_as_thinking_event_not_to_chat():
    seen_events = []
    chat_text: list[str] = []
    agent = Agent(_ReasoningProvider(), Registry(), model="m")

    result = agent.run(
        "2+2?", on_text_delta=chat_text.append, event_listener=seen_events.append
    )

    thinking = [e for e in seen_events if isinstance(e, ThinkingDelta)]
    assert [t.text for t in thinking] == ["let me think… ", "2+2 is 4."]
    # Reasoning must NOT leak into the chat-facing text channel.
    joined_chat = "".join(chat_text)
    assert "think" not in joined_chat
    assert joined_chat == "The answer is 4."
    assert result.text == "The answer is 4."


# ---- wire-layer parsing of the `reasoning` delta field ----


@dataclass
class _Delta:
    content: str | None = None
    reasoning: str | None = None
    reasoning_content: str | None = None
    tool_calls: list = field(default_factory=list)


@dataclass
class _Choice:
    delta: _Delta
    finish_reason: str | None = None


@dataclass
class _Chunk:
    choices: list
    usage: object | None = None


class _StreamChat:
    def __init__(self, chunks):  # noqa: ANN001
        self._chunks = chunks

    def create(self, **kwargs):  # noqa: ANN003
        return iter(self._chunks)


class _NS:
    def __init__(self, **kw):  # noqa: ANN003
        self.__dict__.update(kw)


def _provider_streaming(chunks) -> OpenAIProvider:  # noqa: ANN001
    client = _NS(base_url="http://x/v1", chat=_NS(completions=_StreamChat(chunks)))
    return OpenAIProvider(client=client)


def test_wire_emits_reasoning_delta_from_reasoning_field():
    chunks = [
        _Chunk(choices=[_Choice(delta=_Delta(reasoning="hmm…"))]),
        _Chunk(choices=[_Choice(delta=_Delta(content="hi"), finish_reason="stop")]),
    ]
    events = list(
        _provider_streaming(chunks).stream_message(
            [Message(role="user", content="x")], model="gpt-x"
        )
    )
    reasoning = [e for e in events if isinstance(e, ReasoningDelta)]
    text = [e for e in events if isinstance(e, TextDelta)]
    assert [r.text for r in reasoning] == ["hmm…"]
    assert [t.text for t in text] == ["hi"]


def test_wire_emits_reasoning_delta_from_reasoning_content_field():
    chunks = [_Chunk(choices=[_Choice(delta=_Delta(reasoning_content="step 1"))])]
    events = list(
        _provider_streaming(chunks).stream_message(
            [Message(role="user", content="x")], model="gpt-x"
        )
    )
    assert any(isinstance(e, ReasoningDelta) and e.text == "step 1" for e in events)
