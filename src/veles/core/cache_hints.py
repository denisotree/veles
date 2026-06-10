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

from typing import Any

CACHE_BREAKPOINT_SENTINEL: str = "​[VELES_CACHE_BREAKPOINT]​"


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


def apply_cache_hints(openai_messages: list[dict[str, Any]], model: str) -> list[dict[str, Any]]:
    """Post-process converted messages so a cache breakpoint reaches the wire.

    For Anthropic targets: splits each system message containing the
    sentinel into a two-block content array with `cache_control` on
    the first block (the stable prefix). For everything else: strips
    the sentinel from system content so non-Anthropic providers never
    see it.

    Operates on the OpenAI Chat Completions wire form (list of dicts
    with `role` / `content`); does not touch tool / assistant / user
    messages.
    """
    is_anthropic = is_anthropic_model(model)
    out: list[dict[str, Any]] = []
    for msg in openai_messages:
        if msg.get("role") != "system":
            out.append(msg)
            continue
        content = msg.get("content")
        if not isinstance(content, str) or CACHE_BREAKPOINT_SENTINEL not in content:
            out.append(msg)
            continue
        if not is_anthropic:
            stripped = content.replace(CACHE_BREAKPOINT_SENTINEL, "")
            out.append({**msg, "content": stripped})
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
    return out
