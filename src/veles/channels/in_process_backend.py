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

from veles.daemon.runner import new_run_handle, run_agent_in_background
from veles.daemon.state import DaemonState

logger = logging.getLogger(__name__)


def _manager_opt_in(prompt: str) -> bool:
    """M122f manager gate for the channel path — opt-in, default OFF
    (`VELES_MANAGER_MODE=1`). Defensive: never raises out into the run loop."""
    try:
        from veles.core.orchestration import should_use_manager

        return should_use_manager(prompt, use_heuristic_default=False)
    except Exception:
        return False


class InProcessRunBackend:
    """`RunBackend` implementation that calls `agent_factory` directly."""

    def __init__(self, state: DaemonState) -> None:
        self._state = state

    async def submit_run(
        self, prompt: str, *, session_id: str | None = None, origin: str | None = None
    ) -> dict[str, Any]:
        handle = new_run_handle(session_id=session_id)
        self._state.add_run(handle)
        # M122f: channel turns route through the manager-spawn orchestrator
        # under the same opt-in as the HTTP path (default OFF; enabled by
        # `VELES_MANAGER_MODE=1`). Falls through to the single-agent path when
        # no worker factory is wired or the gate is off.
        if self._state.worker_agent_factory is not None and _manager_opt_in(prompt):
            from veles.daemon.runner import run_manager_in_background

            task = asyncio.create_task(
                run_manager_in_background(
                    handle,
                    worker_agent_factory=self._state.worker_agent_factory,
                    prompt=prompt,
                )
            )
            self._state.run_tasks.add(task)
            task.add_done_callback(self._state.run_tasks.discard)
            return {"run_id": handle.run_id, "session_id": handle.session_id}
        agent = self._state.agent_factory(session_id, prompt=prompt)
        task = asyncio.create_task(
            run_agent_in_background(
                handle,
                agent=agent,
                prompt=prompt,
                post_turn_hook=self._state.post_turn_hook,
                verify_hook=self._state.verify_hook,
                origin=origin,
            )
        )
        self._state.run_tasks.add(task)
        task.add_done_callback(self._state.run_tasks.discard)
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
        """In-process equivalent of `DaemonClient.get_session`. Returns
        `{"session_id", "overrides"}` so the gateway can resolve the
        active model for the /model picker."""
        overrides = self._state.get_overrides(session_id)
        return {
            "session_id": session_id,
            "overrides": overrides.to_dict() if overrides else None,
        }

    async def update_session(
        self,
        session_id: str,
        *,
        model: str | None = None,
        mode: str | None = None,
        provider: str | None = None,
    ) -> dict[str, Any]:
        """In-process equivalent of `DaemonClient.update_session`.

        Writes directly to `state.session_overrides` so the next agent
        build picks up the override — same path the HTTP PATCH handler
        takes. Validation is intentionally lighter than the HTTP variant
        because the only caller is the gateway's inline-keyboard tap,
        which never produces unvalidated user input here."""
        if model is None and mode is None and provider is None:
            raise ValueError("update_session requires at least one of model/mode/provider")
        overrides = self._state.set_overrides(session_id, model=model, mode=mode, provider=provider)
        # Mirror the format of `daemon/server.py:_handle_patch_session`
        # so log scrapers can match a single regex regardless of the
        # backend (HTTP or in-process).
        logger.info(
            "in-process session=%s overrides=%s",
            session_id,
            overrides.to_dict(),
        )
        return {
            "session_id": session_id,
            "overrides": overrides.to_dict(),
        }

    async def health(self) -> dict[str, Any]:
        """In-process equivalent of `DaemonClient.health`. The gateway
        calls this to learn the daemon's fixed provider for /model."""
        return {
            "status": "ok",
            "project": self._state.project.name,
            "provider": self._state.provider,
        }

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
        if choice not in pending.valid_choices:
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
