"""Mirror (M74) — record cross-channel deliveries in the receiving session.

When a scheduler job or `send_message` tool sends text to a chat outside the
session that originated it, the agent on the receiving side won't see the
context unless we append it to that side's transcript. `mirror_to_session`
inserts one synthetic `system` turn with a small header so the agent can
distinguish mirror-injected context from real user input.

Kept intentionally tiny — one function, no class. We only need the append,
not dataclasses or broadcast-fanout logic.
"""

from __future__ import annotations

from veles.core.memory import SessionStore
from veles.core.provider import Message


def mirror_to_session(
    store: SessionStore,
    *,
    session_id: str,
    text: str,
    source: str,
    kind: str = "delivery",
) -> int:
    """Append a `system`-role mirror turn to `session_id`.

    The body is:

        [mirror:<kind> from <source>]
        <text>

    `source` is a free-form label (e.g. `"telegram:42"`, `"job:daily-summary"`)
    so the agent can decide whether to act on the mirrored context. Returns
    the new turn's seq number.
    """
    if not text.strip():
        return -1
    header = f"[mirror:{kind} from {source}]"
    body = f"{header}\n{text}"
    return store.append_turn(session_id, Message(role="system", content=body))


__all__ = ["mirror_to_session"]
