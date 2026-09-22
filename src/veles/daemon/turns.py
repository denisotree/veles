"""Start one agent turn on the daemon — the single entry both front doors share.

`POST /v1/runs` (`server.py::_handle_create_run`) and the in-process channel
backend (`channels/in_process_backend.py::submit_run`) each carried their own
copy of "manager gate → build agent → run in background", and the copies had
already drifted. M280 routes agent modes through here, so there has to be one
place to route them.

What still differs between the two callers is passed in explicitly rather than
unified silently: only the HTTP path touches daemon activity on finish and
delivers to a `deliver_to` target.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from veles.daemon.runner import (
    RunHandle,
    new_run_handle,
    run_agent_in_background,
    run_manager_in_background,
)
from veles.daemon.state import DaemonState

logger = logging.getLogger(__name__)


def manager_opt_in(prompt: str) -> bool:
    """M122f manager gate — opt-in, default OFF (`VELES_MANAGER_MODE=1`), so
    daemon and channel turns never silently fan out to N sub-agents. Never
    raises into the run loop."""
    try:
        from veles.core.orchestration import should_use_manager

        return should_use_manager(prompt, use_heuristic_default=False)
    except Exception:
        return False


def start_turn(
    state: DaemonState,
    *,
    prompt: str,
    session_id: str | None,
    origin: str | None,
    on_finished: Callable[[RunHandle], None] | None = None,
    deliver_hook: Callable[[str], Awaitable[None]] | None = None,
) -> RunHandle:
    """Register a run and start it in the background; returns its handle.

    Building the agent can fail (bad provider config, …). The handle is then
    marked failed — it used to stay "pending" forever on the channel path — and
    the original exception propagates for the caller to report.
    """
    handle = new_run_handle(session_id=session_id)
    state.add_run(handle)

    if state.worker_agent_factory is not None and manager_opt_in(prompt):
        _spawn(
            state,
            run_manager_in_background(
                handle,
                worker_agent_factory=state.worker_agent_factory,
                prompt=prompt,
                on_finished=on_finished,
                verify_hook=state.verify_hook,
                origin=origin,
                store=state.store,
                deliver_hook=deliver_hook,
            ),
        )
        return handle

    try:
        agent = state.agent_factory(session_id, prompt=prompt)
    except Exception as exc:
        handle.state = "failed"
        handle.error = f"{type(exc).__name__}: {exc}"
        handle.finished_at = time.time()
        raise

    # The factory allocates the session eagerly (fresh id for a new chat, or a
    # re-allocated one when the caller's id was stale), so the real session id
    # is known BEFORE the run starts. Adopt it on the handle now so `started`
    # carries it and channels can persist the chat→session mapping even if the
    # turn later errors — otherwise the next message started fresh (amnesia).
    effective_session_id = getattr(agent, "session_id", None) or session_id
    handle.session_id = effective_session_id
    _spawn(
        state,
        run_agent_in_background(
            handle,
            agent=agent,
            prompt=prompt,
            on_finished=on_finished,
            post_turn_hook=state.post_turn_hook,
            verify_hook=state.verify_hook,
            origin=origin,
            # M204: sub-agent factory (delegate/wiki_add under the daemon) +
            # per-session serialization against background-op resume turns.
            subagent_factory=getattr(state, "subagent_factory", None),
            turn_lock=(state.session_lock(effective_session_id) if effective_session_id else None),
            deliver_hook=deliver_hook,
        ),
    )
    return handle


def _spawn(state: DaemonState, coro: Any) -> None:
    task = asyncio.create_task(coro)
    state.run_tasks.add(task)
    task.add_done_callback(state.run_tasks.discard)


__all__ = ["manager_opt_in", "start_turn"]
