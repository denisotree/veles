"""Anthropic prompt-cache breakpoint utilities.

PLAN.md §3.3 + §10: the AGENTS.md+INDEX.md prefix is stable across
turns within a session; the memory-context block that M22 injects is
dynamic per turn. Anthropic's prompt-cache lets the stable prefix
hit a cached read on every turn after the first if we mark the
breakpoint between the two with `cache_control: {"type": "ephemeral"}`.

Veles surfaces this as a sentinel string the CLI inserts between the
two halves of the system prompt. The OpenRouter adapter
post-processes converted messages: when the target model is on
Anthropic AND a system message contains the sentinel, it splits the
content into a two-block array with `cache_control` on the first
block. For any other provider the sentinel is stripped so it never
reaches the wire.

The sentinel is wrapped in zero-width spaces so it stays out of the
visible body if anything ever logs the raw prompt — a surprising
LLM rarely emits ZWSP, and humans never see it.
"""

from __future__ import annotations

import os
from typing import Any

CACHE_BREAKPOINT_SENTINEL: str = "​[VELES_CACHE_BREAKPOINT]​"


# M220: the rolling cache breakpoint may sit on a trailing `tool` message, not
# just the last `user` turn — in a tool-heavy agentic loop the tool results
# since the last user turn are re-billed uncached every iteration, and that is
# the dominant remaining token cost. Marking the tool tail caches them too.
#
# Wire-acceptance of `cache_control` on a `tool`-role content array via
# OpenRouter was unverified when M178 shipped, so this is a *bonus* path with a
# self-heal: `VELES_CACHE_TOOL_TAIL=0` disables it up front, and the provider
# disables it at runtime (via `disable_tool_tail`) the first time a request 400s
# on `cache_control`, then retries — a rejection can never break an agentic turn.
_TOOL_TAIL_ENABLED: bool = os.environ.get("VELES_CACHE_TOOL_TAIL", "1").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
)


def tool_tail_enabled() -> bool:
    return _TOOL_TAIL_ENABLED


def disable_tool_tail() -> None:
    """Self-heal hook: stop marking the tool tail for the rest of the process
    after the wire rejected `cache_control` on a tool message once."""
    global _TOOL_TAIL_ENABLED
    _TOOL_TAIL_ENABLED = False


def _reset_tool_tail(enabled: bool = True) -> None:
    """Test helper — restore the process toggle between cases."""
    global _TOOL_TAIL_ENABLED
    _TOOL_TAIL_ENABLED = enabled


def is_anthropic_model(model: str) -> bool:
    """True for any model that should receive cache_control hints.

    Currently: OpenRouter `anthropic/...` slugs and any model whose
    name contains `claude`. Other providers (OpenAI, Gemini) ignore
    `cache_control`, so we only mark the breakpoint when the relay
    actually uses it.
    """
    if not model:
        return False
    lower = model.lower()
    return lower.startswith("anthropic/") or "claude" in lower


def inject_breakpoint(prefix: str, suffix: str) -> str:
    """Combine `prefix` and `suffix` with the sentinel in between.

    Returns just `prefix` if `suffix` is empty — no point marking a
    cache boundary when there's nothing dynamic after it.
    """
    if not suffix:
        return prefix
    return f"{prefix}{CACHE_BREAKPOINT_SENTINEL}{suffix}"


def split_at_breakpoint(text: str) -> tuple[str, str | None]:
    """Return `(before, after)`; `after` is `None` when the sentinel is absent.

    Only the first occurrence is treated as a breakpoint — the cache
    granularity Anthropic supports is up to four breakpoints per
    request, but for now Veles only needs one (stable / dynamic).
    """
    if CACHE_BREAKPOINT_SENTINEL not in text:
        return text, None
    before, after = text.split(CACHE_BREAKPOINT_SENTINEL, 1)
    return before, after


def build_anthropic_system_blocks(system_text: str | None) -> str | list[dict[str, Any]] | None:
    """Convert a system string to Anthropic's native `system=` shape with cache hint.

    Direct Anthropic adapter (M42b) bypass: instead of going through the
    OpenAI-shape `apply_cache_hints` (which only triggers when a relay
    forwards `cache_control` blocks to Anthropic), the AnthropicProvider
    builds the request body itself. Anthropic accepts `system=` as
    either a plain string or a list of content blocks; we use the list
    form whenever the M35 sentinel is present so the stable prefix gets
    `cache_control: {"type": "ephemeral"}`.

    Returns:
        - `None` when the input is `None` or empty.
        - The original string when the sentinel is absent (no caching needed).
        - A 1-block list `[{"type": "text", "text": suffix}]` when the
          sentinel sits at the start (empty prefix — no point caching
          nothing; the suffix wraps anyway).
        - A 1-block list with `cache_control` when the sentinel sits at
          the end (no dynamic suffix).
        - A 2-block list `[{stable+cache_control}, {dynamic}]` for the
          normal case.
    """
    if not system_text:
        return None
    if CACHE_BREAKPOINT_SENTINEL not in system_text:
        return system_text
    prefix, suffix = split_at_breakpoint(system_text)
    suffix_clean = (suffix or "").strip()
    if not prefix.strip():
        if not suffix_clean:
            return None
        return [{"type": "text", "text": suffix or ""}]
    blocks: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": prefix,
            "cache_control": {"type": "ephemeral"},
        }
    ]
    if suffix_clean:
        blocks.append({"type": "text", "text": suffix or ""})
    return blocks


def strip_cache_sentinel(openai_messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove the breakpoint sentinel from every string-content message.

    The base (and local) adapters don't emit `cache_control` blocks, but the
    system prompt still carries the ZWSP sentinel — without this it would
    leak verbatim into the model's prompt (and, being a constant, slightly
    perturb the prefix). Local backends do their own automatic prefix
    KV-caching, so a clean, stable prefix is all they need (M178).
    """
    out: list[dict[str, Any]] = []
    for msg in openai_messages:
        content = msg.get("content")
        if isinstance(content, str) and CACHE_BREAKPOINT_SENTINEL in content:
            out.append({**msg, "content": content.replace(CACHE_BREAKPOINT_SENTINEL, "")})
        else:
            out.append(msg)
    return out


def _mark_message_tail(openai_messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add an ephemeral `cache_control` breakpoint to the most-recent cacheable
    turn (the "rolling" breakpoint that keeps the growing conversation prefix
    cached — M178).

    Eligible roles: `user` always, and `tool` when the M220 tool-tail toggle is
    on (`tool_tail_enabled()`). Whichever eligible message is *latest* is marked
    — one breakpoint at the furthest-forward stable point, so a tool-heavy loop
    caches its tool results too instead of re-billing them every iteration.
    Assistant turns carrying `tool_calls` have null/array content and are never
    eligible. Combined with the system breakpoint that's ≤2 of Anthropic's 4.
    """
    allow_tool = tool_tail_enabled()
    for i in range(len(openai_messages) - 1, -1, -1):
        msg = openai_messages[i]
        role = msg.get("role")
        if role != "user" and not (role == "tool" and allow_tool):
            continue
        content = msg.get("content")
        if not isinstance(content, str) or not content:
            continue
        block = {"type": "text", "text": content, "cache_control": {"type": "ephemeral"}}
        out = list(openai_messages)
        out[i] = {**msg, "content": [block]}
        return out
    return openai_messages


def apply_cache_hints(openai_messages: list[dict[str, Any]], model: str) -> list[dict[str, Any]]:
    """Post-process converted messages so cache breakpoints reach the wire.

    For Anthropic targets: (1) splits each system message containing the
    sentinel into a two-block content array with `cache_control` on the
    first block (the stable prefix), and (2) adds a rolling `cache_control`
    breakpoint on the most-recent `user`/`tool` message so the growing
    conversation prefix is cached too (M178). For everything else: strips
    the sentinel so non-Anthropic providers never see it.

    Operates on the OpenAI Chat Completions wire form (list of dicts with
    `role` / `content`).
    """
    is_anthropic = is_anthropic_model(model)
    if not is_anthropic:
        return strip_cache_sentinel(openai_messages)
    out: list[dict[str, Any]] = []
    for msg in openai_messages:
        if msg.get("role") != "system":
            out.append(msg)
            continue
        content = msg.get("content")
        if not isinstance(content, str) or CACHE_BREAKPOINT_SENTINEL not in content:
            out.append(msg)
            continue
        prefix, suffix = split_at_breakpoint(content)
        blocks: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": prefix,
                "cache_control": {"type": "ephemeral"},
            }
        ]
        if suffix and suffix.strip():
            blocks.append({"type": "text", "text": suffix})
        out.append({**msg, "content": blocks})
    return _mark_message_tail(out)
