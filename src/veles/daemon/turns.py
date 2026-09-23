"""Start one agent turn on the daemon — the single entry both front doors share.

`POST /v1/runs` (`server.py::_handle_create_run`) and the in-process channel
backend (`daemon/in_process_backend.py::submit_run`) each carried their own
copy of "manager gate → build agent → run in background", and the copies had
already drifted. M280 routes agent modes through here, so there has to be one
place to route them.

What still differs between the two callers is passed in explicitly rather than
unified silently: only the HTTP path touches daemon activity on finish and
delivers to a `deliver_to` target.

The session's agent mode (`DaemonState.chat_modes`, set by `PATCH
/v1/sessions/{id}` / Telegram `/mode`) picks the path: none → the plain
single-agent turn, unchanged, with the manager gate; a chosen mode → the turn
runs through that mode (`daemon/mode_turn.py`) and the manager gate is skipped.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from veles.daemon.mode_turn import make_mode_turn
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


async def start_turn(
    state: DaemonState,
    *,
    prompt: str,
    session_id: str | None,
    origin: str | None,
    on_finished: Callable[[RunHandle], None] | None = None,
    deliver_hook: Callable[[str], Awaitable[None]] | None = None,
    mode: str | None = None,
) -> RunHandle:
    """Register a run and start it in the background; returns its handle.

    `mode` switches the session to that agent mode before the turn (Telegram
    `/goal <task>`: the task is the goal's first message). A chat that has
    never spoken has no session yet, so one is allocated for it here — the
    channel maps the chat to it from the run's `started` event.

    Building the agent can fail (bad provider config, …). The handle is then
    marked failed — it used to stay "pending" forever on the channel path — and
    the original exception propagates for the caller to report.

    The agent is built **off the event loop**. Its system prompt runs memory
    recall through the M264 bridge (`core/memory/aio.py`), which refuses to
    block a running loop — building it here, on the loop, failed every chat
    turn with text from 0.36.0 to 0.39.0. It is also real work (recall, skills,
    the session probe) that has no business stalling every other request.
    """
    if mode is not None:
        if session_id is None:
            session_id = state.store.create_session()
        state.set_chat_mode(session_id, mode)  # an unknown mode raises before any run
    handle = new_run_handle(session_id=session_id)
    state.add_run(handle)
    chosen_mode = state.chat_mode(session_id).mode

    # An explicitly chosen agent mode wins over the manager heuristic: the user
    # asked for planning / writing / … on this chat, not for a fan-out.
    if chosen_mode is None and state.worker_agent_factory is not None and manager_opt_in(prompt):
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

    agent = None
    turn = None
    try:
        if chosen_mode is None:
            agent = await asyncio.to_thread(state.agent_factory, session_id, prompt=prompt)
            # The factory allocates the session eagerly (fresh id for a new chat,
            # or a re-allocated one when the caller's id was stale).
            effective_session_id = getattr(agent, "session_id", None) or session_id
        else:
            assert session_id is not None  # a mode is only ever set on a session
            effective_session_id = _session_for_mode_turn(state, session_id)
            turn = make_mode_turn(state, session_id=effective_session_id, prompt=prompt)
    except Exception as exc:
        handle.state = "failed"
        handle.error = f"{type(exc).__name__}: {exc}"
        handle.finished_at = time.time()
        raise

    # The real session id is known BEFORE the run starts. Adopt it on the handle
    # now so `started` carries it and channels can persist the chat→session
    # mapping even if the turn later errors — otherwise the next message started
    # fresh (amnesia).
    handle.session_id = effective_session_id
    _spawn(
        state,
        run_agent_in_background(
            handle,
            agent=agent,
            turn=turn,
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
            ask_channel=asks_questions(origin),
        ),
    )
    return handle


# Channels whose gateway renders a `clarification_prompt` and takes the reply.
_QUESTION_CHANNELS = frozenset({"telegram"})


def asks_questions(origin: str | None) -> bool:
    """M284: may the agent's `ask_user` wait for an answer from this turn's
    origin? Only a chat that renders the question can; an HTTP caller or a
    scheduled job gets "no human available" at once, as before, instead of a
    run stalled for the prompt timeout."""
    return bool(origin) and origin.split(":", 1)[0] in _QUESTION_CHANNELS  # type: ignore[union-attr]


def _session_for_mode_turn(state: DaemonState, session_id: str) -> str:
    """The session a mode turn runs in, allocated once for the whole turn —
    a mode builds several agents per turn and none may mint its own.

    A channel's map can outlive a session row (DB reset), as
    `_build_agent_for_turn` handles on the default path: a stale id gets a
    fresh session, and the chat's mode moves with it instead of being lost."""
    if state.store.session_exists(session_id):
        return session_id
    fresh = state.store.create_session()
    logger.warning("stale session_id %s for a mode turn; continuing in %s", session_id, fresh)
    moved = state.chat_modes.pop(session_id, None)
    if moved is not None:
        state.chat_modes[fresh] = moved
        state.save_chat_modes()
    return fresh


def _spawn(state: DaemonState, coro: Any) -> None:
    task = asyncio.create_task(coro)
    state.run_tasks.add(task)
    task.add_done_callback(state.run_tasks.discard)


__all__ = ["manager_opt_in", "start_turn"]
