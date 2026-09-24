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
import logging
import secrets
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from concurrent.futures import Future
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from veles.core.agent import Agent, RunResult

if TYPE_CHECKING:
    from veles.core.orchestration import ManagerRunResult
    from veles.core.provider import Message


@dataclass(slots=True)
class PendingPrompt:
    """One outstanding permission prompt waiting for a channel reply.

    The worker thread blocks on `future.result(timeout)`; the HTTP
    endpoint `POST /v1/runs/{id}/prompts/{pid}` resolves the future
    when the channel reports the user's choice. `kind` is `"trust"`,
    `"approval"`, `"critical"` (M213) or `"clarification"` (M284, the
    agent's `ask_user`); `valid_choices` is the whitelist the endpoint
    validates against, unless `free_text` — a question accepts any answer
    typed in reply, its options being only suggestions."""

    kind: str
    tool: str
    valid_choices: tuple[str, ...]
    future: Future[str] = field(default_factory=Future)
    created_at: float = field(default_factory=time.time)
    free_text: bool = False

    def accepts(self, choice: str) -> bool:
        return self.free_text or choice in self.valid_choices


def _no_human_available(question: str, options: list[str] | None = None) -> str | None:
    """`ask_user` answer for a run no chat can answer: none, at once."""
    del question, options
    return None


def _make_run_id() -> str:
    return f"run-{int(time.time()):010d}-{secrets.token_hex(4)}"


RunState = Literal["pending", "running", "completed", "failed"]


@dataclass(slots=True)
class RunHandle:
    run_id: str
    session_id: str | None
    state: RunState = "pending"
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    error: str | None = None
    final_text: str | None = None
    # M234: set when a `deliver_to` delivery was attempted and failed. Best-effort
    # telemetry, deliberately NOT part of the run's success/failure — a chat that
    # can't be reached says nothing about whether the agent did its work. Note the
    # inherent race: `state` becomes "completed" before the delivery is attempted,
    # so a poller that stops at "completed" may read this while a send is still in
    # flight. Same contract as `job_runner`'s `delivery_err`.
    delivery_error: str | None = None
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

    def mark_failed(self, error: str) -> None:
        self.state = "failed"
        self.error = error
        self.finished_at = time.time()

    def mark_completed(
        self, *, text: str, iterations: int, stopped_reason: str | None, session_id: str | None
    ) -> None:
        self.state = "completed"
        self.final_text = text
        self.iterations = iterations
        self.stopped_reason = stopped_reason
        self.session_id = session_id or self.session_id
        self.finished_at = time.time()

    def append_event(self, event: dict[str, Any]) -> None:
        """Append on the event loop. Wake any subscribers."""
        self.events.append(event)
        self.event_added.set()
        self.event_added.clear()

    async def iter_events(self) -> AsyncIterator[dict[str, Any]]:
        """Every event of this run in order, from the first — a late reader gets
        the replay — ending with the terminal `completed`/`error` event."""
        cursor = 0
        while True:
            while cursor < len(self.events):
                event = self.events[cursor]
                cursor += 1
                yield event
                if event.get("type") in ("completed", "error"):
                    return
            if self.done.is_set():
                # The terminal event is appended via call_soon_threadsafe just
                # before `done` is set, so it may still be queued: drain pending
                # callbacks once before concluding there is nothing left.
                await asyncio.sleep(0)
                if cursor >= len(self.events):
                    return
                continue
            await self.event_added.wait()

    def resolve_prompt(self, prompt_id: str, choice: str) -> None:
        """Answer a pending permission prompt or question.

        Raises `LookupError` when `prompt_id` is not pending (answered, timed
        out or never asked) and `ValueError` when `choice` is not one this
        prompt accepts — the prompt then stays pending for a valid answer."""
        pending = self.pending_prompts.pop(prompt_id, None)
        if pending is None:
            raise LookupError(f"prompt {prompt_id!r} not pending")
        if not pending.accepts(choice):
            self.pending_prompts[prompt_id] = pending
            raise ValueError(f"choice {choice!r} not valid for {pending.kind} prompt")
        pending.future.set_result(choice)
        self.append_event({"type": "prompt_resolved", "prompt_id": prompt_id, "choice": choice})


# M234. Bounded so a hung send cannot outlive the shutdown drain, which waits
# `wait_for(handle.done.wait(), timeout=10.0)` per handle (`server.py`). A larger
# budget would be cancelled by that drain mid-send — the message is lost AND
# `delivery_error` stays empty, because a cancellation is not an exception we
# catch. Keep this comfortably under the drain's 10s.
_DELIVER_TIMEOUT_SEC = 8.0


async def _run_deliver_hook(
    handle: RunHandle,
    deliver_hook: Callable[[str], Awaitable[None]] | None,
) -> None:
    """Push the finished answer to the caller's `deliver_to` target. Best-effort.

    Called on the success path only, between the `completed` event and
    `done.set()`: before `done` so the shutdown drain covers the send, and only on
    success so the failure branches need no guard of their own.

    The empty-text guard is load-bearing — `stopped_reason == "empty"` reaches this
    same branch with `result.text == ""`, and Telegram rejects an empty message, so
    without it a run that legitimately said nothing would record a delivery failure.
    """
    if deliver_hook is None or not handle.final_text:
        return
    try:
        await asyncio.wait_for(deliver_hook(handle.final_text), timeout=_DELIVER_TIMEOUT_SEC)
    except Exception as exc:
        # Deliberately not `contextlib.suppress` (the idiom used elsewhere in this
        # file): the exception text is exactly what the caller needs to see.
        handle.delivery_error = f"delivery failed: {type(exc).__name__}: {exc}"
        logging.getLogger("veles.daemon").warning("run %s delivery failed: %s", handle.run_id, exc)


Poster = Callable[[dict[str, Any]], None]


def _settle(handle: RunHandle, on_finished: Callable[[RunHandle], None] | None) -> None:
    """Mark the run over: wake every reader one last time, then notify the caller."""
    handle.done.set()
    handle.event_added.set()
    if on_finished is not None:
        on_finished(handle)


def _fail(
    handle: RunHandle,
    error: str,
    post: Poster,
    on_finished: Callable[[RunHandle], None] | None,
    **event_fields: Any,
) -> None:
    """End the run as failed with an `error` event carrying `event_fields`."""
    handle.mark_failed(error)
    post({"type": "error", "error": error, **event_fields})
    _settle(handle, on_finished)


async def _complete(
    handle: RunHandle,
    *,
    text: str,
    iterations: int,
    stopped_reason: str | None,
    session_id: str | None,
    post: Poster,
    deliver_hook: Callable[[str], Awaitable[None]] | None,
    on_finished: Callable[[RunHandle], None] | None,
) -> None:
    """End the run as completed: the `completed` event, the `deliver_to` push,
    then settle — delivery before `done` so the shutdown drain covers it."""
    handle.mark_completed(
        text=text, iterations=iterations, stopped_reason=stopped_reason, session_id=session_id
    )
    post(
        {
            "type": "completed",
            "stopped_reason": stopped_reason,
            "iterations": iterations,
            "text": text,
            "session_id": handle.session_id,
        }
    )
    await _run_deliver_hook(handle, deliver_hook)
    _settle(handle, on_finished)


# One turn driven by something other than a bare `agent.run` — an agent mode
# (M280, `daemon/mode_turn.py`). Called in the worker thread with the text
# sink, the typed-event sink, and a raw poster for extra event dicts.
TurnFn = Callable[
    [Callable[[str], None], Callable[[Any], None], Callable[[dict[str, Any]], None]],
    RunResult,
]


async def run_agent_in_background(  # noqa: PLR0913
    handle: RunHandle,
    *,
    agent: Agent | None = None,
    turn: TurnFn | None = None,
    prompt: str,
    on_finished: Callable[[RunHandle], None] | None = None,
    post_turn_hook: Callable[[RunResult], None] | None = None,
    verify_hook: Callable[[str, RunResult], RunResult] | None = None,
    origin: str | None = None,
    subagent_factory: Callable[..., Any] | None = None,
    turn_lock: asyncio.Lock | None = None,
    deliver_hook: Callable[[str], Awaitable[None]] | None = None,
    ask_channel: bool = False,
) -> None:
    """Drive `agent.run(prompt)` to completion, mirroring events into `handle`.

    Returns when the agent thread has finished. Exceptions are captured
    into `handle.error` rather than re-raised so the gather'd task never
    crashes the daemon.

    `subagent_factory` (M204): installed via `set_subagent_factory` around the
    turn (the ContextVar reaches the worker thread through `to_thread`), so
    `delegate`/`wiki_add` can spawn sub-agents under the daemon — this used to
    be REPL-only. `turn_lock` (M204): when given, the WHOLE turn runs under it —
    the per-session serializer that lets a background-op RESUME turn queue
    behind a live user turn instead of racing it on one session history.

    `turn` (M280) replaces `agent` when an agent mode drives the turn; exactly
    one of the two is given. Everything else — prompters, trust turn, locks,
    hooks — is shared. A mode's phase-transition turn returns a
    `stopped_reason == "synthetic"` result: nothing was asked of the model, so
    `verify_hook` and `post_turn_hook` (insight extraction) are skipped for it.
    """
    if (agent is None) == (turn is None):
        raise ValueError("run_agent_in_background needs exactly one of agent= or turn=")
    loop = asyncio.get_running_loop()
    if turn_lock is not None:
        await turn_lock.acquire()

    def _post(event: dict[str, Any]) -> None:
        loop.call_soon_threadsafe(handle.append_event, event)

    def _on_text_delta(delta: str) -> None:
        _post({"type": "text_delta", "delta": delta})

    def _on_event(ev: Any) -> None:
        # Forward the first-action signal so channels can show a contextual
        # "on it" ack (tool call → "searching…" etc.) instead of a bare "...".
        # Only tool_call is forwarded — the rest of the event stream stays as
        # text_delta/completed/error to keep WS consumers unchanged.
        if getattr(ev, "type", None) == "tool_call":
            _post(
                {
                    "type": "tool_call",
                    "name": getattr(ev, "name", ""),
                    "tool_call_id": getattr(ev, "tool_call_id", ""),
                }
            )

    handle.state = "running"
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
    from veles.core.context import reset_origin, set_origin
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

    # M166: the originating chat (e.g. "telegram:<id>") as a delivery target,
    # so tools like `task_add` can default `deliver_to` to "this chat". Set
    # before the worker thread starts — `asyncio.to_thread` copies the context,
    # so the agent's tools see it.
    origin_token = set_origin(origin)
    # M204: the sub-agent factory, so delegate/wiki_add can spawn workers under
    # the daemon (used to be REPL-only). Same ContextVar mechanism as origin.
    from veles.core.orchestration.delegation import (
        reset_subagent_factory,
        set_subagent_factory,
    )

    subagent_token = (
        set_subagent_factory(subagent_factory) if subagent_factory is not None else None
    )
    # The unified prompter carries `arguments` and `reason` to the
    # Telegram trust-prompt render and serves both trust and approval.
    unified_token = set_unified_prompter(make_unified_prompter(handle, loop))
    # M213: critical-ops confirms (M39 always-confirm + the M198 exfiltration
    # gate) get the same channel round-trip as approval — an inline keyboard
    # instead of the daemon's M212 auto-deny. Deny on timeout stays the
    # fail-closed floor.
    from veles.core.critical_ops import (
        reset_critical_confirmer,
        set_critical_confirmer,
    )
    from veles.daemon.channel_prompter import make_critical_confirmer

    critical_token = set_critical_confirmer(make_critical_confirmer(handle, loop))
    # M148: ask_user must never reach the default stdin prompter here — a
    # foreground `veles channel run` has a TTY and would block on the
    # *operator's* stdin. M284: a chat that can answer gets the question as a
    # `clarification_prompt`; anything else still hears "no human available"
    # at once instead of waiting out the prompt timeout.
    from veles.daemon.channel_prompter import make_question_prompter

    question_token = set_question_prompter(
        make_question_prompter(handle, loop) if ask_channel else _no_human_available
    )
    turn_token = begin_trust_turn()

    def _worker() -> RunResult:
        if turn is not None:
            return turn(_on_text_delta, _on_event, _post)
        assert agent is not None
        return agent.run(prompt, on_text_delta=_on_text_delta, event_listener=_on_event)

    try:
        try:
            result = await asyncio.to_thread(_worker)
        except Exception as exc:
            # Carry the session id on the error too: the session was already
            # allocated (and the user turn persisted) before the failure, so
            # the channel should keep the chat→session mapping and continue
            # the same session on the next message rather than starting fresh.
            _fail(
                handle,
                f"{type(exc).__name__}: {exc}",
                _post,
                on_finished,
                session_id=handle.session_id,
            )
            return

        # M170b: opt-in verify→escalate before the `completed` event, so
        # channels render the corrected answer and `post_turn_hook` ingests
        # it. Runs off the event loop (the advisor + escalation re-run hit
        # the LLM). Best-effort: a hook failure keeps the base result — a
        # broken advisor must never wedge a turn.
        synthetic = result.stopped_reason == "synthetic"
        if verify_hook is not None and not synthetic:
            with contextlib.suppress(Exception):
                result = await asyncio.to_thread(verify_hook, prompt, result)

        # A blank answer even after the answer nudge goes to the daemon log (the
        # one channel operators watch) instead of vanishing silently.
        if result.stopped_reason == "empty":
            logging.getLogger("veles.daemon").warning(
                "run %s finished with an EMPTY answer (session=%s, iterations=%d) — "
                "the model produced no text even after the answer nudge",
                handle.run_id,
                result.session_id or handle.session_id,
                result.iterations,
            )
        await _complete(
            handle,
            text=result.text,
            iterations=result.iterations,
            stopped_reason=result.stopped_reason,
            session_id=result.session_id,
            post=_post,
            deliver_hook=deliver_hook,
            on_finished=on_finished,
        )
        if post_turn_hook is not None and not synthetic:
            # Run the learning loop off the event loop — it may hit the LLM
            # (insight extractor) and shouldn't block aiohttp request handlers.
            with contextlib.suppress(Exception):
                await asyncio.to_thread(post_turn_hook, result)
    finally:
        end_trust_turn(turn_token)
        reset_origin(origin_token)
        if subagent_token is not None:
            reset_subagent_factory(subagent_token)
        reset_unified_prompter(unified_token)
        reset_critical_confirmer(critical_token)
        reset_question_prompter(question_token)
        # Any prompt still pending at this point is orphaned (the agent
        # finished before the user answered). Cancel the futures so any
        # in-flight HTTP POST gets a clean 410 rather than 200 on a
        # stale receiver, and so blocked worker threads can't leak.
        for pid, pending in list(handle.pending_prompts.items()):
            pending.future.cancel()
            handle.pending_prompts.pop(pid, None)
        if turn_lock is not None:
            turn_lock.release()


def new_run_handle(*, session_id: str | None = None) -> RunHandle:
    return RunHandle(run_id=_make_run_id(), session_id=session_id)


async def run_manager_in_background(
    handle: RunHandle,
    *,
    worker_agent_factory: Callable[..., Agent],
    prompt: str,
    on_finished: Callable[[RunHandle], None] | None = None,
    verify_hook: Callable[[str, RunResult], RunResult] | None = None,
    origin: str | None = None,
    store: Any | None = None,
    deliver_hook: Callable[[str], Awaitable[None]] | None = None,
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

    M170c: the opt-in `verify_hook` now applies here too — the writer's
    `final_text` is adapted into a `RunResult` (evidence = the writer
    session's messages, loaded best-effort from `store`) so the same
    advisor judge+escalate as the direct path runs on the synthesised
    answer. `origin` is set for the worker context so a worker's
    `task_add`/`job_add` can default `deliver_to` to the originating chat.

    Still skips `post_turn_hook` — aggregating one parent RunResult across
    N sub-sessions for the learning loop is a M124b problem; workers' own
    sessions get curated on their next idle cycle.
    """
    from veles.core.context import reset_origin, set_origin
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

    def _worker() -> ManagerRunResult:
        return decompose_and_run(prompt, agent_factory=worker_agent_factory)

    # M170c: set origin before the worker thread starts — `asyncio.to_thread`
    # copies the context, so workers' tools see the originating chat.
    origin_token = set_origin(origin)
    try:
        try:
            result = await asyncio.to_thread(_worker)
        except Exception as exc:
            _fail(handle, f"manager: {type(exc).__name__}: {exc}", _post, on_finished)
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
            _fail(handle, result.error or "manager produced no output", _post, on_finished)
            return

        writer_handle = result.handles[-1] if result.handles else None
        writer_session = writer_handle.session_id if writer_handle else None
        final_text = result.final_text

        # M170c: opt-in verify→escalate on the manager's synthesised answer.
        # Adapt the manager result into a RunResult so the same verify_hook as
        # the direct path judges it. Evidence = the writer session's messages
        # (best-effort; verify still judges text-only if unavailable). The
        # escalation re-runs the prompt on the advisor model continuing the
        # writer session. Best-effort: a broken advisor keeps the base answer.
        if verify_hook is not None:
            history: list[Message] = []
            if store is not None and writer_session:
                with contextlib.suppress(Exception):
                    history = store.load_messages(writer_session)
            synth = RunResult(
                text=final_text,
                iterations=len(result.handles),
                history=history,
                session_id=writer_session,
            )
            with contextlib.suppress(Exception):
                verified = await asyncio.to_thread(verify_hook, prompt, synth)
                final_text = verified.text
                writer_session = verified.session_id or writer_session

        # Emit the (possibly escalated) text as one final delta + completed
        # event so channels' existing buffering machinery picks it up unchanged.
        _post({"type": "text_delta", "delta": final_text})
        await _complete(
            handle,
            text=final_text,
            iterations=len(result.handles),
            stopped_reason="completed",
            session_id=writer_session,
            post=_post,
            deliver_hook=deliver_hook,
            on_finished=on_finished,
        )
    finally:
        reset_origin(origin_token)


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
