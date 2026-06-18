"""Cross-channel runtime protocols.

The Telegram gateway used to type its backend as `Any` — implicit duck
typing against `DaemonClient` (HTTP loopback) and `InProcessRunBackend`
(asyncio dispatch inside the daemon). M-R2.7 formalises the contract:
both backends now declare themselves `RunBackend`, and the gateway's
type hint reflects that. Strictly structural — no runtime import cost
because `Protocol` is checked at type-time only.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class RunBackend(Protocol):
    """Two-method surface the gateways need: submit a prompt, then
    follow its event stream until completion."""

    async def submit_run(
        self, prompt: str, *, session_id: str | None = None, origin: str | None = None
    ) -> dict[str, Any]:
        """POST one turn. Returns at least `{"run_id": ..., "session_id": ...}`.

        `origin` (M166) is the originating chat as a delivery target
        (e.g. "telegram:<id>") so reminder tools can default to "this chat"."""
        ...

    def stream_events(self, run_id: str) -> AsyncIterator[dict[str, Any]]:
        """Yield typed event dicts until the run completes or errors.

        Events: `started`, `text_delta`, `tool_call`, `completed`,
        `error`, `trust_prompt`, `approval_prompt`, `prompt_resolved`.
        Older backends may emit only the first five; new event types
        from M-channel-prompts onward extend the stream without
        breaking forward-compat."""
        ...

    async def submit_prompt_answer(
        self, run_id: str, prompt_id: str, choice: str
    ) -> dict[str, Any]:
        """Resolve an outstanding `trust_prompt` / `approval_prompt`.

        Channels call this when the user picks a button. Backends that
        never emit prompts can stub it as `raise NotImplementedError`;
        the gateway only calls this in response to a prompt event."""
        ...


__all__ = ["RunBackend"]
