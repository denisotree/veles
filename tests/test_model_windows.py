"""M177 — per-model context-window registry, live-occupancy usage tracking,
and the emergency-truncation guard the TUI now enables.
"""

from __future__ import annotations

from dataclasses import dataclass

from veles.core.agent import UsageSnapshot
from veles.core.context_compressor import emergency_truncate, estimate_tokens
from veles.core.model_windows import context_window_for, default_hard_ceiling_for
from veles.core.provider import Message

# ---- context-window registry ----


def test_haiku_is_200k():
    assert context_window_for("anthropic/claude-haiku-4.5") == 200_000


def test_sonnet_and_opus_46plus_are_1m():
    assert context_window_for("anthropic/claude-sonnet-4.6") == 1_000_000
    assert context_window_for("claude-opus-4-8") == 1_000_000


def test_gpt4o_is_128k():
    assert context_window_for("openai/gpt-4o") == 128_000


def test_unknown_and_none_default_to_200k():
    assert context_window_for(None) == 200_000
    assert context_window_for("some/unknown-model") == 200_000


def test_hard_ceiling_is_90_percent():
    assert default_hard_ceiling_for("anthropic/claude-haiku-4.5") == 180_000
    assert default_hard_ceiling_for("claude-opus-4-8") == 900_000


# ---- UsageSnapshot.last_prompt_tokens (overwrite, not sum) ----


@dataclass
class _U:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0


def test_last_prompt_tokens_tracks_latest_not_cumulative():
    snap = UsageSnapshot()
    snap.add(_U(prompt_tokens=10_000, completion_tokens=500, total_tokens=10_500))
    snap.add(_U(prompt_tokens=42_000, completion_tokens=800, total_tokens=42_800))
    # prompt_tokens accumulates; last_prompt_tokens is the latest request only.
    assert snap.prompt_tokens == 52_000
    assert snap.last_prompt_tokens == 42_000


# ---- emergency truncation guard (enabled in the TUI via hard_ceiling) ----


def _big_turn(role: str, n: int) -> Message:
    return Message(role=role, content="x" * n)


def test_emergency_truncate_brings_history_under_ceiling():
    history = [Message(role="system", content="system prompt")]
    # ~10 turns of ~4k tokens each (16k chars / 4) → ~40k estimated tokens.
    for i in range(10):
        history.append(_big_turn("user" if i % 2 == 0 else "assistant", 16_000))
    target = 10_000
    assert estimate_tokens(history) > target
    truncated, dropped = emergency_truncate(history, target_tokens=target)
    assert dropped > 0
    assert estimate_tokens(truncated) <= target
    # The system message is preserved as the head.
    assert truncated[0].role == "system"


def test_emergency_truncate_noop_when_under_target():
    history = [Message(role="system", content="hi"), Message(role="user", content="short")]
    truncated, dropped = emergency_truncate(history, target_tokens=100_000)
    assert dropped == 0
    assert truncated == history
