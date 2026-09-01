"""Repair tool_call ↔ tool_result pairing before a provider call.

Providers (OpenAI / Azure, Anthropic) reject a request whose history has an
assistant `tool_call` without a matching tool-result message — the
``No tool output found for function call ...`` HTTP 400 — or a tool-result
message with no preceding tool_call. Veles' own dispatch always pairs them
(`tool_dispatch._dispatch` returns a tool message on every branch), but context
compression, emergency truncation, a resumed session loaded from the store, or a
provider-side translation quirk can split a pair. This pass makes the history
self-consistent right before it goes on the wire:

  - an assistant tool_call with no result → a placeholder tool result is
    synthesised immediately after the assistant message;
  - a tool result with no matching tool_call anywhere → dropped.

Idempotent (a second pass is a no-op) and O(n). Fenced mode records assistant
turns with no native ``tool_calls`` (calls live in the text), so this is a
no-op there.
"""

from __future__ import annotations

import hashlib
import json
import re

from veles.core.provider import Message

_PLACEHOLDER = "<tool result unavailable — not recorded>"

# ---- M238: supersede stale tool results ------------------------------------
#
# Read a file on turn 2, read it again on turn 9 and BOTH results stay in the
# history — the stale one keeps competing for attention with the fresh one.
# SKILL.state (arXiv 2608.26263) measured what that costs: after the world
# changes underneath the agent, history-based runtimes hallucinate for 5-8
# consecutive turns because "obsolete facts in their prompt history overpower
# contradictory new observations". Veles had no dedup and no invalidation at
# all, on either dispatch path.
#
# So: when a deterministic read is repeated with identical arguments, blank the
# EARLIER result down to a one-line marker. The message itself stays — deleting
# a `role="tool"` message would orphan its `tool_call_id` and `repair_tool_pairing`
# above would have to synthesise it back.
#
# Only deterministic reads qualify. `run_shell` and `fetch_url` are deliberately
# absent: the same command can legitimately return different output over time
# (that difference is often the point), so superseding would destroy evidence
# rather than a duplicate.
_SUPERSEDABLE_TOOLS = frozenset({"read_file", "list_files", "stat_file", "search_files"})

_SUPERSEDED = "<superseded by a newer identical {name} call>"

# Fenced mode collapses every result into one `role="user"` message as
# `[name]\ncontent` chunks and keeps no arguments anywhere in the history, so a
# key cannot be recovered after the fact the way the native path recovers it
# from `assistant.tool_calls`. The short tag below is therefore written INTO the
# chunk header at dispatch time; it is what makes the fenced path superseder-able.
_FENCED_CHUNK_RE = "\\[{name} {tag}\\]\\n.*?(?=\\n\\n\\[|\\Z)"


def call_key(name: str, arguments: object) -> str:
    """Stable short tag for a (tool, arguments) pair.

    `json.dumps(sort_keys=True)` so argument order can't produce two keys for
    one call; `default=str` so a non-serialisable argument degrades to its repr
    instead of raising inside the dispatch loop.
    """
    try:
        payload = json.dumps(arguments, sort_keys=True, ensure_ascii=False, default=str)
    except (TypeError, ValueError):  # pragma: no cover - default=str covers ~everything
        payload = repr(arguments)
    digest = hashlib.sha256(f"{name}\x00{payload}".encode()).hexdigest()[:8]
    return f"#{digest}"


def supersede_native(history: list[Message], name: str, arguments: object) -> int:
    """Blank earlier `role="tool"` results for the same (tool, arguments).

    The key is recovered from the history itself: assistant messages carry the
    `ToolCall`s with id + name + arguments, so `tool_call_id` on a tool message
    identifies exactly which call produced it. Returns how many were superseded.
    """
    if name not in _SUPERSEDABLE_TOOLS:
        return 0
    target = call_key(name, arguments)
    by_id = {
        tc.id: call_key(tc.name, tc.arguments) for m in history for tc in m.tool_calls if tc.id
    }
    marker = _SUPERSEDED.format(name=name)
    superseded = 0
    for m in history:
        if m.role != "tool" or m.tool_call_id is None:
            continue
        if by_id.get(m.tool_call_id) != target or m.content == marker:
            continue
        m.content = marker
        superseded += 1
    return superseded


def supersede_loaded_history(history: list[Message], header: str) -> int:
    """Collapse duplicate reads across a whole history, keeping the last of each.

    M245: `supersede_native` / `supersede_fenced` fire at dispatch time and edit
    the in-memory list, but `_persist` has already written the full result to
    the append-only `SessionStore`. So `--resume` used to rehydrate every stale
    copy and hand the model back the contradictions M238 had just removed.

    Superseding on *load* fixes that without an update path on the store — and
    the store stays a complete archive, which is what `curator.py` and
    `insight_extractor.py` mine. The model sees the pruned view; the record
    keeps everything.

    Walks each duplicate group and blanks all but the LAST occurrence, mirroring
    dispatch-time semantics (the freshest read wins).
    """
    by_id = {
        tc.id: call_key(tc.name, tc.arguments)
        for m in history
        for tc in m.tool_calls
        if tc.id and tc.name in _SUPERSEDABLE_TOOLS
    }

    # native: index every tool message by its call key, keep the last per key.
    native: dict[str, list[int]] = {}
    for i, m in enumerate(history):
        if m.role != "tool" or m.tool_call_id is None:
            continue
        key = by_id.get(m.tool_call_id)
        if key is not None:
            native.setdefault(key, []).append(i)

    name_by_id: dict[str, str] = {
        str(tc.id): tc.name for m in history for tc in m.tool_calls if tc.id
    }
    superseded = 0
    for positions in native.values():
        for i in positions[:-1]:
            msg = history[i]
            marker = _SUPERSEDED.format(name=name_by_id.get(str(msg.tool_call_id), "tool"))
            if msg.content != marker:
                msg.content = marker
                superseded += 1

    # fenced: the tag lives in the chunk header, so replay dispatch order —
    # every earlier occurrence of a tag is superseded by a later one.
    seen_tags: list[tuple[str, str]] = []
    for m in history:
        if m.role != "user" or not (m.content or "").startswith(header):
            continue
        for name, tag in re.findall(r"\[([a-z_]+) (#[0-9a-f]{8})\]", m.content or ""):
            seen_tags.append((name, tag))
    counts: dict[tuple[str, str], int] = {}
    for pair in seen_tags:
        counts[pair] = counts.get(pair, 0) + 1
    for (name, tag), n in counts.items():
        if n < 2 or name not in _SUPERSEDABLE_TOOLS:
            continue
        # Supersede every occurrence but the last: run the single-target
        # superseder n-1 times is wrong (it blanks all), so drop the final
        # message from the slice instead.
        last_idx = max(
            i
            for i, m in enumerate(history)
            if m.role == "user"
            and (m.content or "").startswith(header)
            and f"[{name} {tag}]" in (m.content or "")
        )
        superseded += supersede_fenced(history[:last_idx], name, tag, header)
    return superseded


def supersede_fenced(history: list[Message], name: str, tag: str, header: str) -> int:
    """Blank earlier fenced chunks tagged `[name #tag]` inside result messages.

    `header` is the fenced result-block header, passed in so this module does
    not import the fenced-tools module (which would invert the dependency).
    """
    if name not in _SUPERSEDABLE_TOOLS:
        return 0
    pattern = re.compile(
        _FENCED_CHUNK_RE.format(name=re.escape(name), tag=re.escape(tag)), re.DOTALL
    )
    replacement = f"[{name} {tag}]\n{_SUPERSEDED.format(name=name)}"
    superseded = 0
    for m in history:
        if m.role != "user" or not (m.content or "").startswith(header):
            continue
        new_content, hits = pattern.subn(replacement, m.content or "")
        if hits and new_content != m.content:
            m.content = new_content
            superseded += hits
    return superseded


def repair_tool_pairing(history: list[Message]) -> list[Message]:
    """Return a history where every assistant tool_call has a matching tool
    result and every tool result has a matching tool_call. Returns the input
    list unchanged (same object) when it is already consistent."""
    call_ids: set[str] = {tc.id for m in history for tc in m.tool_calls}
    result_ids: set[str] = {
        m.tool_call_id for m in history if m.role == "tool" and m.tool_call_id is not None
    }

    orphan_result = any(
        m.role == "tool" and (m.tool_call_id is None or m.tool_call_id not in call_ids)
        for m in history
    )
    unanswered_call = any(cid not in result_ids for cid in call_ids)
    if not orphan_result and not unanswered_call:
        return history  # already consistent — no allocation

    repaired: list[Message] = []
    for m in history:
        if m.role == "tool" and (m.tool_call_id is None or m.tool_call_id not in call_ids):
            continue  # orphaned tool result → drop
        repaired.append(m)
        if m.role == "assistant" and m.tool_calls:
            for tc in m.tool_calls:
                if tc.id not in result_ids:
                    repaired.append(Message(role="tool", content=_PLACEHOLDER, tool_call_id=tc.id))
    return repaired
