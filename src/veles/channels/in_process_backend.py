"""In-process run backend for channels co-hosted inside the daemon.

`TelegramGateway` was originally written against `DaemonClient`, which
talks HTTP/WS to a remote daemon. When the gateway lives *inside* the
daemon's own asyncio loop, going through localhost would mean spinning
up an aiohttp client + a daemon bearer token for no reason.

`InProcessRunBackend` exposes the same two methods the gateway uses
(`submit_run`, `stream_events`) but dispatches directly against the
daemon's `AgentFactory` + `RunHandle` plumbing. Drop-in compatible with
the gateway's `RunBackend` protocol.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from veles.daemon.state import DaemonState
from veles.daemon.turns import start_turn

logger = logging.getLogger(__name__)


class InProcessRunBackend:
    """`RunBackend` implementation that calls `agent_factory` directly."""

    def __init__(self, state: DaemonState) -> None:
        self._state = state

    async def submit_run(
        self,
        prompt: str,
        *,
        session_id: str | None = None,
        origin: str | None = None,
        mode: str | None = None,
    ) -> dict[str, Any]:
        # Same entry as `POST /v1/runs` (manager gate, agent build, background
        # run). A channel turn neither touches daemon activity nor carries a
        # `deliver_to` — the gateway streams the answer itself. `mode` switches
        # the session first (`/goal <task>`).
        handle = await start_turn(
            self._state, prompt=prompt, session_id=session_id, origin=origin, mode=mode
        )
        return {"run_id": handle.run_id, "session_id": handle.session_id}

    async def stream_events(self, run_id: str) -> AsyncIterator[dict[str, Any]]:
        handle = self._state.get_run(run_id)
        if handle is None:
            raise LookupError(f"unknown run_id: {run_id!r}")
        cursor = 0
        while True:
            while cursor < len(handle.events):
                event = handle.events[cursor]
                cursor += 1
                yield event
                if event.get("type") in ("completed", "error"):
                    return
            if handle.done.is_set() and cursor >= len(handle.events):
                # The terminal event is appended via call_soon_threadsafe just
                # before `done` is set, so it may still be queued. Drain pending
                # callbacks before closing, else a fast run's completion event
                # is lost to this subscriber.
                await asyncio.sleep(0)
                if cursor >= len(handle.events):
                    return
                continue
            await handle.event_added.wait()

    async def get_session(self, session_id: str) -> dict[str, Any]:
        """In-process equivalent of `DaemonClient.get_session`: the session's
        agent mode (`"default"` when never switched) and its goal, if any."""
        return {
            "session_id": session_id,
            "mode": self._state.chat_mode(session_id).mode or "default",
            "goal": self._state.chat_goal(session_id),
        }

    async def cancel_goal(self, session_id: str) -> dict[str, Any]:
        """In-process equivalent of `DaemonClient.cancel_goal`: cancel the
        chat's goal; `{"cancelled": null}` when it had none."""
        goal = self._state.cancel_chat_goal(session_id, reason="cancelled from the chat")
        return {"session_id": session_id, "cancelled": goal}

    async def update_session(self, session_id: str, *, mode: str) -> dict[str, Any]:
        """In-process equivalent of `DaemonClient.update_session` (PATCH):
        switch the session's agent mode; `"default"` switches it back. An
        unknown mode raises `ValueError`, as the HTTP route answers 400."""
        self._state.set_chat_mode(session_id, None if mode == "default" else mode)
        # Same line format as `server.py::_handle_patch_session`, so one log
        # regex matches either backend.
        logger.info("in-process session=%s mode=%s", session_id, mode)
        return {"session_id": session_id, "mode": mode}

    async def health(self) -> dict[str, Any]:
        """In-process equivalent of `DaemonClient.health`. The gateway
        calls this to learn the daemon's fixed provider for /model."""
        return {
            "status": "ok",
            "project": self._state.project.name,
            "provider": self._state.provider,
        }

    async def run_dream(self) -> dict[str, Any]:
        """In-process equivalent of `DaemonClient.run_dream`."""
        runner = self._state.dream_runner
        if runner is None:
            raise RuntimeError("the dream runner is not enabled on this daemon")
        result = await runner.force_run()
        return {"summary": result.summary(), "notes": result.notes}

    async def submit_prompt_answer(
        self, run_id: str, prompt_id: str, choice: str
    ) -> dict[str, Any]:
        """In-process equivalent of `DaemonClient.submit_prompt_answer`.

        Looks up the PendingPrompt on the run's handle and resolves its
        future directly — no HTTP hop. The gateway uses the same code
        path as the HTTP variant; this keeps the channel agnostic of
        whether the daemon is local or remote."""
        handle = self._state.get_run(run_id)
        if handle is None:
            raise LookupError(f"unknown run_id: {run_id!r}")
        pending = handle.pending_prompts.pop(prompt_id, None)
        if pending is None:
            raise LookupError(f"prompt {prompt_id!r} not pending on run {run_id!r}")
        if not pending.accepts(choice):
            # Restore so a follow-up call with a valid key can resolve.
            handle.pending_prompts[prompt_id] = pending
            raise ValueError(f"choice {choice!r} not valid for {pending.kind} prompt")
        pending.future.set_result(choice)
        handle.append_event(
            {
                "type": "prompt_resolved",
                "prompt_id": prompt_id,
                "choice": choice,
            }
        )
        return {"accepted": True, "choice": choice}


__all__ = ["InProcessRunBackend"]
