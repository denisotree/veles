"""Daemon runner (M51) — `Agent.run` as a managed, observable background task.

`Agent.run` is synchronous and feeds text chunks through an
`on_text_delta` callback. The daemon needs to:

1. fire-and-forget a run so the POST handler returns quickly with a
   run_id;
2. fan streaming events out to one or more WebSocket subscribers, with
   replay for late joiners;
3. capture the final `RunResult` (text + iterations + stopped_reason)
   so `GET /v1/runs/{id}` can report it after completion.

`RunHandle` owns the event buffer and an `asyncio.Event` that fires on
every new event. Subscribers walk the buffer with a cursor and `await`
the event between drains, so a client connecting after the run finishes
still receives every event in order (the event fires once on completion
to wake any remaining waiters).

The Agent.run worker executes inside a thread (`asyncio.to_thread`)
because the agent loop is fully synchronous; the `on_text_delta`
callback hops back onto the event loop via
`asyncio.run_coroutine_threadsafe` to mutate the buffer + fire the
event safely.
"""

from __future__ import annotations

import asyncio
import contextlib
import secrets
import time
from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass, field
from typing import Any

from veles.core.agent import Agent, RunResult


@dataclass(slots=True)
class PendingPrompt:
    """One outstanding permission prompt waiting for a channel reply.

    The worker thread blocks on `future.result(timeout)`; the HTTP
    endpoint `POST /v1/runs/{id}/prompts/{pid}` resolves the future
    when the channel reports the user's choice. `kind` is
    `"trust"` or `"approval"`; `valid_choices` is the whitelist the
    endpoint validates against."""

    kind: str
    tool: str
    valid_choices: tuple[str, ...]
    future: Future[str] = field(default_factory=Future)
    created_at: float = field(default_factory=time.time)


def _make_run_id() -> str:
    return f"run-{int(time.time()):010d}-{secrets.token_hex(4)}"


@dataclass(slots=True)
class RunHandle:
    run_id: str
    session_id: str | None
    state: str = "pending"  # pending | running | completed | failed
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    error: str | None = None
    final_text: str | None = None
    iterations: int = 0
    stopped_reason: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    event_added: asyncio.Event = field(default_factory=asyncio.Event)
    done: asyncio.Event = field(default_factory=asyncio.Event)
    pending_prompts: dict[str, PendingPrompt] = field(default_factory=dict)

    def to_summary(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "session_id": self.session_id,
            "state": self.state,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "iterations": self.iterations,
            "stopped_reason": self.stopped_reason,
            "error": self.error,
        }

    def append_event(self, event: dict[str, Any]) -> None:
        """Append on the event loop. Wake any subscribers."""
        self.events.append(event)
        self.event_added.set()
        self.event_added.clear()


async def run_agent_in_background(
    handle: RunHandle,
    *,
    agent: Agent,
    prompt: str,
    on_finished: Callable[[RunHandle], None] | None = None,
    post_turn_hook: Callable[[RunResult], None] | None = None,
) -> None:
    """Drive `agent.run(prompt)` to completion, mirroring events into `handle`.

    Returns when the agent thread has finished. Exceptions are captured
    into `handle.error` rather than re-raised so the gather'd task never
    crashes the daemon.
    """
    loop = asyncio.get_running_loop()

    def _post(event: dict[str, Any]) -> None:
        loop.call_soon_threadsafe(handle.append_event, event)

    def _on_text_delta(delta: str) -> None:
        _post({"type": "text_delta", "delta": delta})

    handle.state = "running"
    handle.session_id = handle.session_id  # placeholder; filled by run if missing
    _post(
        {
            "type": "started",
            "run_id": handle.run_id,
            "session_id": handle.session_id,
        }
    )

    # Install channel-aware prompters BEFORE the worker thread starts.
    # `asyncio.to_thread` carries the current `copy_context`, so the
    # ContextVar overrides reach the agent's permission engine.
    # Channels that subscribe to the WS stream see `trust_prompt` /
    # `approval_prompt` events and POST the user's answer back via
    # `/v1/runs/{run_id}/prompts/{prompt_id}` — see channel_prompter.py.
    from veles.core.permission.prompt import (
        reset_prompter as reset_unified_prompter,
    )
    from veles.core.permission.prompt import (
        set_prompter as set_unified_prompter,
    )
    from veles.core.trust import begin_trust_turn, end_trust_turn
    from veles.core.user_prompt import (
        reset_question_prompter,
        set_question_prompter,
    )
    from veles.daemon.channel_prompter import make_unified_prompter

    # The unified prompter carries `arguments` and `reason` to the
    # Telegram trust-prompt render and serves both trust and approval.
    unified_token = set_unified_prompter(make_unified_prompter(handle, loop))
    # M148: ask_user must not reach the default stdin prompter on the daemon /
    # channel path — a foreground `veles channel run` has a TTY and would block
    # on the *operator's* stdin instead of asking the channel user. Skip for
    # now (→ "proceed on best assumption"); routing the question to the channel
    # is M148b.
    question_token = set_question_prompter(lambda _q: None)
    turn_token = begin_trust_turn()

    def _worker() -> RunResult:
        return agent.run(prompt, on_text_delta=_on_text_delta)

    try:
        try:
            result = await asyncio.to_thread(_worker)
        except Exception as exc:
            handle.state = "failed"
            handle.error = f"{type(exc).__name__}: {exc}"
            handle.finished_at = time.time()
            _post({"type": "error", "error": handle.error})
            handle.done.set()
            # Wake any waiting subscribers one last time.
            handle.event_added.set()
            if on_finished is not None:
                on_finished(handle)
            return

        handle.state = "completed"
        handle.iterations = result.iterations
        handle.stopped_reason = result.stopped_reason
        handle.final_text = result.text
        handle.session_id = result.session_id or handle.session_id
        handle.finished_at = time.time()
        _post(
            {
                "type": "completed",
                "stopped_reason": result.stopped_reason,
                "iterations": result.iterations,
                "text": result.text,
                "session_id": handle.session_id,
            }
        )
        handle.done.set()
        handle.event_added.set()
        if on_finished is not None:
            on_finished(handle)
        if post_turn_hook is not None:
            # Run the learning loop off the event loop — it may hit the LLM
            # (insight extractor) and shouldn't block aiohttp request handlers.
            with contextlib.suppress(Exception):
                await asyncio.to_thread(post_turn_hook, result)
    finally:
        end_trust_turn(turn_token)
        reset_unified_prompter(unified_token)
        reset_question_prompter(question_token)
        # Any prompt still pending at this point is orphaned (the agent
        # finished before the user answered). Cancel the futures so any
        # in-flight HTTP POST gets a clean 410 rather than 200 on a
        # stale receiver, and so blocked worker threads can't leak.
        for pid, pending in list(handle.pending_prompts.items()):
            pending.future.cancel()
            handle.pending_prompts.pop(pid, None)


def new_run_handle(*, session_id: str | None = None) -> RunHandle:
    return RunHandle(run_id=_make_run_id(), session_id=session_id)


async def run_manager_in_background(
    handle: RunHandle,
    *,
    worker_agent_factory: Callable[..., Agent],
    prompt: str,
    on_finished: Callable[[RunHandle], None] | None = None,
) -> None:
    """M124: drive `decompose_and_run(prompt)` to completion, mirroring
    plan/step events into `handle`.

    Differences from `run_agent_in_background`:
    - Workers run synchronously inside a worker thread (decompose_and_run
      is sync); we don't stream per-token deltas — the writer's output
      arrives as one final `text_delta` followed by `completed`.
    - Emits a `manager_plan` event after dispatch so channels can show
      "Decomposing into N workers" before the writer text lands.
    - Errors fall through: caller decides whether to retry via the
      legacy direct path.

    Skips `post_turn_hook` — workers' own sessions get curated on
    their next idle cycle; aggregating one parent RunResult across N
    sub-sessions is a M124b problem.
    """
    from veles.core.orchestration import decompose_and_run

    loop = asyncio.get_running_loop()

    def _post(event: dict[str, Any]) -> None:
        loop.call_soon_threadsafe(handle.append_event, event)

    handle.state = "running"
    _post(
        {
            "type": "started",
            "run_id": handle.run_id,
            "session_id": handle.session_id,
        }
    )

    def _worker():
        return decompose_and_run(prompt, agent_factory=worker_agent_factory)

    try:
        result = await asyncio.to_thread(_worker)
    except Exception as exc:
        handle.state = "failed"
        handle.error = f"manager: {type(exc).__name__}: {exc}"
        handle.finished_at = time.time()
        _post({"type": "error", "error": handle.error})
        handle.done.set()
        handle.event_added.set()
        if on_finished is not None:
            on_finished(handle)
        return

    # Plan event — channels show "🧠 Decomposing into N workers..."
    plan = result.plan
    _post(
        {
            "type": "manager_plan",
            "objective": plan.objective,
            "steps": [
                {
                    "role": step.role,
                    "status": step.status,
                    "session_id": step.session_id,
                    "rationale": step.rationale,
                }
                for step in plan.steps
            ],
        }
    )

    if result.error or not result.final_text:
        handle.state = "failed"
        handle.error = result.error or "manager produced no output"
        handle.finished_at = time.time()
        _post({"type": "error", "error": handle.error})
        handle.done.set()
        handle.event_added.set()
        if on_finished is not None:
            on_finished(handle)
        return

    # Emit the writer's text as one final delta + completed event so
    # channels' existing buffering machinery picks it up unchanged.
    _post({"type": "text_delta", "delta": result.final_text})

    writer_handle = result.handles[-1] if result.handles else None
    writer_session = writer_handle.session_id if writer_handle else None
    handle.state = "completed"
    handle.iterations = len(result.handles)
    handle.stopped_reason = "completed"
    handle.final_text = result.final_text
    handle.session_id = writer_session or handle.session_id
    handle.finished_at = time.time()
    _post(
        {
            "type": "completed",
            "stopped_reason": "completed",
            "iterations": handle.iterations,
            "text": result.final_text,
            "session_id": handle.session_id,
        }
    )
    handle.done.set()
    handle.event_added.set()
    if on_finished is not None:
        on_finished(handle)


__all__ = [
    "AgentFactory",
    "RunHandle",
    "new_run_handle",
    "run_agent_in_background",
    "run_manager_in_background",
]


AgentFactory = Callable[..., Agent]
"""Signature: `factory(session_id, *, prompt=None) -> Agent` — daemon delegates Agent
construction so tests can inject stub providers."""
