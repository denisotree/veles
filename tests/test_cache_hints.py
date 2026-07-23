"""M35 — Anthropic prompt-cache breakpoint utilities.

Tests the model detector, sentinel injection/splitting helpers, and
the post-pass that mutates converted system messages into a
two-block content array with `cache_control` for Anthropic targets.
"""

from __future__ import annotations

import pytest

from veles.core.cache_hints import (
    CACHE_BREAKPOINT_SENTINEL,
    _reset_tool_tail,
    apply_cache_hints,
    build_anthropic_system_blocks,
    disable_tool_tail,
    inject_breakpoint,
    is_anthropic_model,
    split_at_breakpoint,
    strip_cache_sentinel,
    tool_tail_enabled,
)


@pytest.fixture(autouse=True)
def _reset_tool_tail_toggle():
    """M220: the tool-tail toggle is process-global (self-heal flips it off).
    Restore it around every test so a `disable_tool_tail()` can't leak."""
    _reset_tool_tail(True)
    yield
    _reset_tool_tail(True)


# ---- is_anthropic_model ----


def test_is_anthropic_matches_anthropic_slug() -> None:
    assert is_anthropic_model("anthropic/claude-sonnet-4.6")


def test_is_anthropic_matches_claude_substring() -> None:
    assert is_anthropic_model("claude-haiku-4-5")


def test_is_anthropic_rejects_openai() -> None:
    assert not is_anthropic_model("openai/gpt-4o")


def test_is_anthropic_rejects_gemini() -> None:
    assert not is_anthropic_model("google/gemini-2.5-pro")


def test_is_anthropic_handles_empty() -> None:
    assert not is_anthropic_model("")


def test_is_anthropic_is_case_insensitive() -> None:
    assert is_anthropic_model("ANTHROPIC/CLAUDE-SONNET")


# ---- inject_breakpoint / split_at_breakpoint ----


def test_inject_breakpoint_joins_with_sentinel() -> None:
    out = inject_breakpoint("stable", "dynamic")
    assert CACHE_BREAKPOINT_SENTINEL in out
    assert out == f"stable{CACHE_BREAKPOINT_SENTINEL}dynamic"


def test_inject_breakpoint_returns_prefix_when_suffix_empty() -> None:
    assert inject_breakpoint("stable", "") == "stable"


def test_split_at_breakpoint_returns_none_when_absent() -> None:
    before, after = split_at_breakpoint("no marker here")
    assert before == "no marker here"
    assert after is None


def test_split_at_breakpoint_splits_first_occurrence() -> None:
    text = inject_breakpoint("a", "b" + CACHE_BREAKPOINT_SENTINEL + "c")
    before, after = split_at_breakpoint(text)
    assert before == "a"
    assert after == "b" + CACHE_BREAKPOINT_SENTINEL + "c"


def test_inject_then_split_roundtrip() -> None:
    before, after = split_at_breakpoint(inject_breakpoint("x", "y"))
    assert before == "x"
    assert after == "y"


# ---- apply_cache_hints ----


def _sys_msg(text: str) -> dict:
    return {"role": "system", "content": text}


def test_apply_anthropic_with_sentinel_emits_two_blocks() -> None:
    msgs = [_sys_msg(inject_breakpoint("stable prefix", "dynamic block"))]
    out = apply_cache_hints(msgs, "anthropic/claude-sonnet-4.6")
    assert out[0]["role"] == "system"
    blocks = out[0]["content"]
    assert isinstance(blocks, list)
    assert blocks[0]["type"] == "text"
    assert blocks[0]["text"] == "stable prefix"
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}
    assert blocks[1]["text"] == "dynamic block"
    assert "cache_control" not in blocks[1]


def test_apply_anthropic_without_sentinel_keeps_string_content() -> None:
    msgs = [_sys_msg("plain prompt no sentinel")]
    out = apply_cache_hints(msgs, "anthropic/claude-sonnet-4.6")
    assert out[0]["content"] == "plain prompt no sentinel"


def test_apply_non_anthropic_strips_sentinel_from_string() -> None:
    msgs = [_sys_msg(inject_breakpoint("stable", "dynamic"))]
    out = apply_cache_hints(msgs, "openai/gpt-4o")
    assert isinstance(out[0]["content"], str)
    assert CACHE_BREAKPOINT_SENTINEL not in out[0]["content"]
    assert out[0]["content"] == "stabledynamic"


def test_apply_marks_last_user_message_tail() -> None:
    """M178: the most-recent user/tool message gets a rolling cache breakpoint
    so the growing conversation prefix is cached. The assistant turn (not
    user/tool) is left untouched; the user message before it is marked."""
    msgs = [
        _sys_msg("system"),
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    out = apply_cache_hints(msgs, "anthropic/claude-sonnet-4.6")
    assert out[2] == msgs[2]  # assistant untouched
    tail = out[1]["content"]
    assert isinstance(tail, list)
    assert tail[0]["text"] == "hi"
    assert tail[0]["cache_control"] == {"type": "ephemeral"}


def test_apply_tail_marks_trailing_tool_when_enabled() -> None:
    """M220: with the tool-tail toggle on (default), the latest `tool` message
    is the rolling breakpoint — its results are cached instead of re-billed
    every agentic iteration. The earlier user turn is not double-marked; the
    assistant-tool-call message (null content) is never eligible."""
    msgs = [
        _sys_msg("system"),
        {"role": "user", "content": "do it"},
        {"role": "assistant", "content": None, "tool_calls": [{"id": "t2"}]},
        {"role": "tool", "content": "tool output", "tool_call_id": "t1"},
    ]
    out = apply_cache_hints(msgs, "anthropic/claude-sonnet-4.6")
    assert out[1] == msgs[1]  # earlier user turn not marked (tool tail is later)
    assert out[2] == msgs[2]  # assistant tool-call untouched
    tail = out[3]["content"]
    assert isinstance(tail, list)
    assert tail[0]["text"] == "tool output"
    assert tail[0]["cache_control"] == {"type": "ephemeral"}


def test_apply_tail_falls_back_to_user_when_tool_tail_disabled() -> None:
    """When tool-tail caching is off (self-healed or VELES_CACHE_TOOL_TAIL=0),
    a trailing tool message is left alone and the last user turn is marked."""
    disable_tool_tail()
    assert tool_tail_enabled() is False
    msgs = [
        _sys_msg("system"),
        {"role": "user", "content": "do it"},
        {"role": "tool", "content": "tool output", "tool_call_id": "t1"},
    ]
    out = apply_cache_hints(msgs, "anthropic/claude-sonnet-4.6")
    assert out[2] == msgs[2]  # tool message untouched
    tail = out[1]["content"]
    assert isinstance(tail, list)
    assert tail[0]["text"] == "do it"


def test_apply_at_most_two_breakpoints() -> None:
    """System split (1) + rolling tail (1) ≤ Anthropic's 4-breakpoint limit."""
    msgs = [
        _sys_msg(inject_breakpoint("stable", "dynamic")),
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "reply"},
        {"role": "user", "content": "second"},
    ]
    out = apply_cache_hints(msgs, "anthropic/claude-sonnet-4.6")
    n = 0
    for m in out:
        content = m.get("content")
        if isinstance(content, list):
            n += sum(1 for b in content if isinstance(b, dict) and "cache_control" in b)
    assert n == 2


def test_apply_non_anthropic_strips_sentinel_and_no_tail() -> None:
    msgs = [
        _sys_msg(inject_breakpoint("stable", "dynamic")),
        {"role": "user", "content": "hi"},
    ]
    out = apply_cache_hints(msgs, "openai/gpt-4o")
    assert isinstance(out[0]["content"], str)
    assert CACHE_BREAKPOINT_SENTINEL not in out[0]["content"]
    assert out[1] == msgs[1]  # no cache_control for non-anthropic


def test_apply_drops_empty_dynamic_suffix() -> None:
    """An empty string after the sentinel collapses to a single-block array."""
    msgs = [_sys_msg(f"stable{CACHE_BREAKPOINT_SENTINEL}")]
    out = apply_cache_hints(msgs, "anthropic/claude-sonnet-4.6")
    blocks = out[0]["content"]
    assert isinstance(blocks, list)
    assert len(blocks) == 1
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}


def test_apply_preserves_other_message_keys() -> None:
    msgs = [{"role": "system", "content": inject_breakpoint("a", "b"), "name": "x"}]
    out = apply_cache_hints(msgs, "anthropic/claude-sonnet-4.6")
    assert out[0].get("name") == "x"


def test_apply_handles_empty_message_list() -> None:
    assert apply_cache_hints([], "anthropic/claude-sonnet-4.6") == []


# ---- strip_cache_sentinel (local / base path) ----


def test_strip_cache_sentinel_removes_marker() -> None:
    msgs = [
        _sys_msg(inject_breakpoint("stable", "dynamic")),
        {"role": "user", "content": "no sentinel here"},
    ]
    out = strip_cache_sentinel(msgs)
    assert out[0]["content"] == "stabledynamic"
    assert CACHE_BREAKPOINT_SENTINEL not in out[0]["content"]
    assert out[1] == msgs[1]


def test_local_prepare_messages_strips_sentinel() -> None:
    """The base (local) `_prepare_messages` must strip the sentinel so it
    never leaks into a local model's prompt."""
    from veles.core.openai_wire import OpenAICompatibleProvider
    from veles.core.provider import Message

    prov = OpenAICompatibleProvider.__new__(OpenAICompatibleProvider)
    msgs = [Message(role="system", content=inject_breakpoint("stable", "dynamic"))]
    out = prov._prepare_messages(msgs, "ollama/llama3")
    assert CACHE_BREAKPOINT_SENTINEL not in out[0]["content"]


# ---------- M42b — build_anthropic_system_blocks ----------


def test_build_blocks_none_returns_none() -> None:
    assert build_anthropic_system_blocks(None) is None


def test_build_blocks_empty_returns_none() -> None:
    assert build_anthropic_system_blocks("") is None


def test_build_blocks_plain_returns_string() -> None:
    assert build_anthropic_system_blocks("just text") == "just text"


def test_build_blocks_with_sentinel_emits_two_blocks() -> None:
    out = build_anthropic_system_blocks("prefix" + CACHE_BREAKPOINT_SENTINEL + "suffix")
    assert out == [
        {"type": "text", "text": "prefix", "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": "suffix"},
    ]


def test_build_blocks_trailing_sentinel_emits_single_cached_block() -> None:
    out = build_anthropic_system_blocks("prefix" + CACHE_BREAKPOINT_SENTINEL)
    assert isinstance(out, list)
    assert len(out) == 1
    assert out[0]["cache_control"] == {"type": "ephemeral"}


def test_build_blocks_leading_sentinel_emits_plain_block() -> None:
    out = build_anthropic_system_blocks(CACHE_BREAKPOINT_SENTINEL + "only dynamic")
    assert isinstance(out, list)
    assert len(out) == 1
    assert "cache_control" not in out[0]
    assert out[0]["text"] == "only dynamic"


def test_build_blocks_only_sentinel_returns_none() -> None:
    assert build_anthropic_system_blocks(CACHE_BREAKPOINT_SENTINEL) is None


def test_build_blocks_first_sentinel_wins() -> None:
    """Only the first sentinel is the breakpoint; later ones land in the dynamic block."""
    out = build_anthropic_system_blocks(
        "A" + CACHE_BREAKPOINT_SENTINEL + "B" + CACHE_BREAKPOINT_SENTINEL + "C"
    )
    assert isinstance(out, list)
    assert out[0]["text"] == "A"
    # The second sentinel is preserved verbatim in the dynamic block —
    # this is unlikely to happen in practice (CLI inserts at most one)
    # but the function shouldn't crash.
    assert CACHE_BREAKPOINT_SENTINEL in out[1]["text"]
