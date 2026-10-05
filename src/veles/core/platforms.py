"""Channel platforms — the contract a channel module implements and what its
gateway talks to.

`RunBackend` is what a gateway needs from the daemon: `DaemonClient` (HTTP
loopback) and `InProcessRunBackend` (asyncio dispatch inside the daemon) both
implement it. It lives in core so `veles.sdk` can hand it to channel modules.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol, runtime_checkable


class RunBackendError(RuntimeError):
    """A run backend (the HTTP daemon client or the in-process one) failed a request."""


@runtime_checkable
class RunBackend(Protocol):
    """What a channel gateway needs from the daemon: submit a prompt, follow its
    event stream, answer its prompts, and read or change the chat's session."""

    async def submit_run(
        self,
        prompt: str,
        *,
        session_id: str | None = None,
        origin: str | None = None,
        mode: str | None = None,
    ) -> dict[str, Any]:
        """POST one turn. Returns at least `{"run_id": ..., "session_id": ...}`.

        `origin` (M166) is the originating chat as a delivery target
        (e.g. "telegram:<id>") so reminder tools can default to "this chat".
        `mode` (M280b) switches the session's agent mode first."""
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

    async def get_session(self, session_id: str) -> dict[str, Any]:
        """The session's agent `mode` (`"default"` when never switched) and its `goal`."""
        ...

    async def update_session(self, session_id: str, *, mode: str) -> dict[str, Any]:
        """Switch the session's agent mode; `"default"` switches it back."""
        ...

    async def cancel_goal(self, session_id: str) -> dict[str, Any]:
        """Cancel the session's goal; `{"cancelled": null}` when it had none."""
        ...

    async def run_dream(self) -> dict[str, Any]:
        """Run a dream cycle now; `{"summary": ..., "notes": ...}`."""
        ...

    async def health(self) -> dict[str, Any]:
        """The daemon's status, project and fixed provider."""
        ...


__all__ = ["RunBackend", "RunBackendError"]
