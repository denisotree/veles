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

from veles.core.provider import Message

_PLACEHOLDER = "<tool result unavailable — not recorded>"


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
