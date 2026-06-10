"""M27 — strip <memory-context>...</memory-context> echoes.

The streaming scrubber must handle tags split across chunk boundaries
(both open and close), unclosed open tags at finalize time, and the
common case of plain text with no tags.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from veles.core.agent import Agent
from veles.core.context_scrubber import (
    CLOSE_TAG,
    OPEN_TAG,
    MemoryContextScrubber,
    scrub_text,
)
from veles.core.provider import (
    ProviderResponse,
    StreamEnd,
    TextDelta,
    TokenUsage,
)
from veles.core.tools.registry import Registry

# ---- scrub_text (one-shot) ----


def test_scrub_text_returns_input_when_no_tags() -> None:
    assert scrub_text("hello world") == "hello world"


def test_scrub_text_strips_inline_block() -> None:
    text = f"prefix {OPEN_TAG}secret data{CLOSE_TAG} suffix"
    assert scrub_text(text) == "prefix  suffix"


def test_scrub_text_strips_multiple_blocks() -> None:
    text = f"a{OPEN_TAG}1{CLOSE_TAG}b{OPEN_TAG}2{CLOSE_TAG}c"
    assert scrub_text(text) == "abc"


def test_scrub_text_drops_unclosed_open_tag_and_tail() -> None:
    text = f"head {OPEN_TAG}leaked content with no close"
    assert scrub_text(text) == "head "


def test_scrub_text_handles_empty_input() -> None:
    assert scrub_text("") == ""


def test_scrub_text_strips_block_with_newlines_inside() -> None:
    text = f"x{OPEN_TAG}line1\nline2\n{CLOSE_TAG}y"
    assert scrub_text(text) == "xy"


# ---- MemoryContextScrubber (streaming) ----


def test_streaming_no_tag_is_passthrough() -> None:
    s = MemoryContextScrubber()
    assert s.feed("hello ") == "hello "
    assert s.feed("world") == "world"
    assert s.finalize() == ""


def test_streaming_strips_intra_chunk_tag() -> None:
    s = MemoryContextScrubber()
    out = s.feed(f"hi {OPEN_TAG}drop{CLOSE_TAG} bye")
    assert out == "hi  bye"
    assert s.finalize() == ""


def test_streaming_strips_open_tag_split_across_chunks() -> None:
    s = MemoryContextScrubber()
    # First chunk ends mid open tag — only the safe prefix flushes.
    out1 = s.feed("hello <memory-")
    assert out1 == "hello "
    out2 = s.feed(f"context>secret{CLOSE_TAG} tail")
    assert out2 == " tail"
    assert s.finalize() == ""


def test_streaming_strips_close_tag_split_across_chunks() -> None:
    s = MemoryContextScrubber()
    out1 = s.feed(f"head {OPEN_TAG}drop")
    assert out1 == "head "
    out2 = s.feed(" more drop </memory-")
    assert out2 == ""
    out3 = s.feed("context> tail")
    assert out3 == " tail"
    assert s.finalize() == ""


def test_streaming_partial_open_at_eos_emitted_literally() -> None:
    """If the stream ends with a partial '<m' that never completed, it was
    real text after all — emit it on finalize."""
    s = MemoryContextScrubber()
    out = s.feed("plain text <m")
    assert out == "plain text "
    assert s.finalize() == "<m"


def test_streaming_unclosed_open_at_eos_drops_tail() -> None:
    s = MemoryContextScrubber()
    out = s.feed(f"head {OPEN_TAG}leaked")
    assert out == "head "
    assert s.finalize() == ""


def test_streaming_handles_multiple_blocks_one_chunk() -> None:
    s = MemoryContextScrubber()
    out = s.feed(f"a{OPEN_TAG}1{CLOSE_TAG}b{OPEN_TAG}2{CLOSE_TAG}c")
    assert out == "abc"
    assert s.finalize() == ""


def test_streaming_lone_lt_passthrough_after_finalize() -> None:
    s = MemoryContextScrubber()
    out = s.feed("a < b")
    # "<" after " " starts no marker prefix; whole chunk is safe.
    assert out == "a < b"
    assert s.finalize() == ""


def test_streaming_byte_by_byte_drip_strips_tag() -> None:
    """Worst-case streaming: one character per chunk."""
    s = MemoryContextScrubber()
    full = f"hi {OPEN_TAG}x{CLOSE_TAG} bye"
    collected: list[str] = []
    for ch in full:
        collected.append(s.feed(ch))
    collected.append(s.finalize())
    assert "".join(collected) == "hi  bye"


# ---- Agent integration ----


def _resp(text: str) -> ProviderResponse:
    return ProviderResponse(
        text=text,
        tool_calls=[],
        usage=TokenUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
        finish_reason="stop",
    )


@dataclass
class _NonStreamingStub:
    name: str = "stub"
    supports_tools: bool = True
    responses: list[ProviderResponse] = field(default_factory=list)
    _idx: int = 0

    def create_message(self, messages, tools=None, *, model: str, max_tokens: int = 4096):
        resp = self.responses[self._idx]
        self._idx += 1
        return resp


@dataclass
class _StreamingStub:
    name: str = "stub-stream"
    supports_tools: bool = True
    chunks: list[str] = field(default_factory=list)
    full: str = ""

    def stream_message(self, messages, tools=None, *, model: str, max_tokens: int = 4096):
        for c in self.chunks:
            yield TextDelta(text=c)
        yield StreamEnd(response=_resp(self.full))


def test_agent_persists_assistant_message_without_memory_context() -> None:
    leaked = f"reply with {OPEN_TAG}should-not-persist{CLOSE_TAG} done"
    provider = _NonStreamingStub(responses=[_resp(leaked)])
    agent = Agent(provider=provider, registry=Registry(), model="m")
    result = agent.run("hi")
    assert result.text == "reply with  done"
    assistant_msgs = [m for m in result.history if m.role == "assistant"]
    assert assistant_msgs[0].content == "reply with  done"


def test_agent_streaming_emits_only_clean_chunks_and_persists_clean_text() -> None:
    full = f"hi {OPEN_TAG}drop{CLOSE_TAG} bye"
    chunks = [f"hi {OPEN_TAG}", "drop", f"{CLOSE_TAG} bye"]
    provider = _StreamingStub(chunks=chunks, full=full)
    agent = Agent(provider=provider, registry=Registry(), model="m")

    emitted: list[str] = []
    result = agent.run("hi", on_text_delta=emitted.append)

    assert "".join(emitted) == "hi  bye"
    assistant_msgs = [m for m in result.history if m.role == "assistant"]
    assert assistant_msgs[0].content == "hi  bye"
