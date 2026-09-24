"""Daemon HTTP + WebSocket server.

`make_app` registers the `/v1/` API: health and status, runs (submit, list,
read, stream events over a WebSocket, answer a pending prompt), sessions
(list, read, delete, set mode, cancel goal), and — from `routes_jobs.py` — the
scheduler's jobs and the dream runner. `make_app(...).router.routes()` is the
authoritative list.

Every endpoint except `/v1/health` is gated by `bearer_auth_middleware`. The
token store is reloaded on every request so out-of-band token CRUD propagates
without a restart. Channel gateways hosted by the daemon start from
`channels.py`.

The app accepts an `AgentFactory` callable so tests can inject stub
providers without touching the network; production wires it in
`daemon/agent_factory.py`.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiohttp import WSMsgType, web

from veles import __version__
from veles.daemon.auth import TokenStore, bearer_auth_middleware
from veles.daemon.channels import chat_session_slot, start_channel_runners
from veles.daemon.http_util import json_object, runner_status
from veles.daemon.routes_jobs import add_job_routes
from veles.daemon.runner import (
    AgentFactory,
)
from veles.daemon.state import CHAT_MODES, DaemonState

logger = logging.getLogger(__name__)


def make_app(state: DaemonState) -> web.Application:
    app = web.Application(middlewares=[bearer_auth_middleware])
    app["state"] = state
    app["token_store"] = state.token_store
    app.on_startup.append(_start_background_runners)
    app.on_shutdown.append(_stop_background_runners)
    app.on_shutdown.append(_drain_in_flight_runs)

    app.router.add_get("/v1/health", _handle_health)
    app.router.add_get("/v1/status", _handle_status)
    app.router.add_get("/v1/channels", _handle_list_channels)
    app.router.add_post("/v1/runs", _handle_create_run)
    app.router.add_get("/v1/runs", _handle_list_runs)
    app.router.add_get("/v1/runs/{run_id}", _handle_get_run)
    app.router.add_get("/v1/runs/{run_id}/events", _handle_run_events_ws)
    app.router.add_post("/v1/runs/{run_id}/prompts/{prompt_id}", _handle_resolve_prompt)
    app.router.add_get("/v1/sessions", _handle_list_sessions)
    app.router.add_get("/v1/sessions/{session_id}", _handle_get_session)
    app.router.add_delete("/v1/sessions/{session_id}", _handle_delete_session)
    app.router.add_patch("/v1/sessions/{session_id}", _handle_patch_session)
    app.router.add_delete("/v1/sessions/{session_id}/goal", _handle_cancel_session_goal)
    add_job_routes(app)
    return app


async def _handle_health(request: web.Request) -> web.Response:
    from veles.core.sanitize import sanitize

    state: DaemonState = request.app["state"]
    # M127: model is fixed at launch from config, so `active_model` is
    # always the daemon's configured model — no per-session overrides
    # resurrect a stale model. Field kept for dashboard back-compat.
    active_model = state.default_model
    return web.json_response(
        {
            "status": "ok",
            "version": __version__,
            # Identity for the detach parent's startup gate: it matches this
            # pid against the child it spawned, so a dying predecessor still
            # holding the port can't pass for the new daemon (live 2026-07-09).
            "pid": os.getpid(),
            "project": state.project.name,
            "project_root": sanitize(str(state.project.root), project=state.project),
            "started_at": state.started_at,
            "provider": state.provider,
            "model": state.default_model,
            "active_model": active_model,
            # The channels actually running (from `state.channel_runners`,
            # not re-derived from config) so the TUI picker reflects reality.
            "channels": list(state.active_channels),
        }
    )


async def _handle_status(request: web.Request) -> web.Response:
    """Extended health (M74): runtime view of runs / jobs / dream / channels.

    Cheap, allocation-light response — callers (TUI, channel ops dashboards)
    poll this every few seconds.
    """
    state: DaemonState = request.app["state"]
    runs = state.list_runs()
    active = sum(1 for h in runs if not h.done.is_set())
    from veles.core.sanitize import sanitize

    return web.json_response(
        {
            "status": "ok",
            "version": __version__,
            "project": state.project.name,
            "project_root": sanitize(str(state.project.root), project=state.project),
            "started_at": state.started_at,
            "last_activity_at": state.last_activity_at,
            "runs": {
                "total": len(runs),
                "active": active,
            },
            "jobs": runner_status(state.job_runner),
            "dream": runner_status(state.dream_runner),
            # The docstring has always promised channels here; surface the
            # actually-running set (M158-followup — was omitted before).
            "channels": list(state.active_channels),
        }
    )


async def _handle_list_channels(request: web.Request) -> web.Response:
    """List channels known to this daemon (M74).

    Sources, in order:
    1. Registered platforms (channel modules whose factory has imported).
    2. Sidecar session-map files at `<user-home>/channels/*-sessions.json` —
       evidence that a channel has been used. Each platform reports its
       persisted chat count.
    """
    from veles.channels.platform_registry import ensure_builtins_registered, list_platforms
    from veles.channels.session_map import (
        SessionMap,
        channel_session_path,
        default_channels_dir,
    )

    ensure_builtins_registered()
    platforms = list_platforms()
    channels_dir = default_channels_dir()
    out: list[dict[str, Any]] = []
    for name in platforms:
        path = channel_session_path(name)
        sessions = 0
        if path.is_file():
            sessions = len(SessionMap.load(path).list())
        out.append({"platform": name, "sessions": sessions, "session_map_path": str(path)})
    # Surface any sidecar files for unregistered platforms (defensive — a
    # channel module may have been uninstalled).
    if channels_dir.is_dir():
        for entry in sorted(channels_dir.glob("*-sessions.json")):
            name = entry.name.removesuffix("-sessions.json")
            if name in platforms:
                continue
            sessions = len(SessionMap.load(entry).list())
            out.append(
                {
                    "platform": name,
                    "sessions": sessions,
                    "session_map_path": str(entry),
                    "registered": False,
                }
            )
    return web.json_response({"channels": out})


# M234. Mirrors the wording of `core/tools/builtin/task_tools.py::_resolve_target`,
# which rejects a bad target at write time so the caller fixes it now rather than
# discovering it at delivery time.
_BAD_TARGET = (
    "{field!r} is not a valid delivery target; use '<platform>:<chat_id>' "
    "(e.g. 'telegram:42') or 'local'"
)


def _resolve_deliver_to(raw: Any, origin: str | None) -> tuple[str | None, str | None]:
    """Validate an incoming `deliver_to`, returning `(target, error)`.

    `"origin"` is **resolved** against the request's own `origin` rather than
    rejected: it keeps this endpoint's vocabulary identical to `task_add`/`job_add`,
    and means the router never sees `kind="origin"` — which matters because no
    `origin_handler` is wired in production, so such a target would raise at
    delivery time. `task_tools._resolve_target` can't be reused for this: it reads
    the `current_origin()` ContextVar, which is unset inside an HTTP handler.
    """
    from veles.core.delivery_target import DeliveryTarget

    if raw is None:
        return None, None
    if not isinstance(raw, str) or not raw.strip():
        return None, "'deliver_to' must be a non-empty string"
    spec = raw.strip()
    if spec == "origin":
        if not origin:
            return None, "'deliver_to' of \"origin\" requires an 'origin' in the same request"
        spec = origin
    try:
        DeliveryTarget.parse(spec)
    except ValueError:
        return None, _BAD_TARGET.format(field="deliver_to")
    return spec, None


async def _handle_create_run(request: web.Request) -> web.Response:
    state: DaemonState = request.app["state"]
    body = await json_object(request)
    if isinstance(body, web.Response):
        return body
    prompt = body.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return web.json_response({"error": "'prompt' (non-empty string) required"}, status=400)
    session_id = body.get("session_id")
    if session_id is not None and not isinstance(session_id, str):
        return web.json_response({"error": "'session_id' must be a string"}, status=400)
    origin = body.get("origin")  # M166: originating chat as a delivery target
    if origin is not None and not isinstance(origin, str):
        return web.json_response({"error": "'origin' must be a string"}, status=400)
    # M234: `origin` is consumed AS a delivery target — `task_add`/`job_add` default
    # their `deliver_to` to it — so it has to satisfy the same grammar. Unvalidated,
    # an HTTP caller could plant a malformed origin that only blows up later, inside
    # an agent tool call. The one production producer already conforms
    # (`telegram:{chat_id}`), so this rejects nothing that works today.
    if origin:
        from veles.core.delivery_target import DeliveryTarget

        try:
            DeliveryTarget.parse(origin)
        except ValueError:
            return web.json_response({"error": _BAD_TARGET.format(field="origin")}, status=400)

    deliver_to, err = _resolve_deliver_to(body.get("deliver_to"), origin)
    if err is not None:
        return web.json_response({"error": err}, status=400)
    # M280b: switch the session's agent mode for this and later turns (the
    # same as PATCH, but usable before the chat has a session).
    mode = body.get("mode")
    if mode is not None and mode not in CHAT_MODES:
        return web.json_response(
            {"error": f"invalid mode {mode!r}", "valid_modes": sorted(CHAT_MODES)}, status=400
        )
    if deliver_to is not None and state.delivery_router is None:
        # Fail loudly rather than accept a delivery contract this daemon cannot
        # honour: no channel is running, so nothing would ever be sent.
        return web.json_response(
            {"error": "no delivery channel is running on this daemon"}, status=503
        )

    def _on_finished(_: Any) -> None:
        state.touch_activity()

    # Filled once the run is registered; `_deliver` runs after the turn, by
    # which time it holds the run's final session id.
    started: dict[str, Any] = {}

    # Built here rather than handing the router to the runner: `daemon/runner.py`
    # stays ignorant of DeliveryRouter, the same way it takes `verify_hook` /
    # `post_turn_hook` instead of the machinery behind them.
    deliver_hook: Callable[[str], Awaitable[None]] | None = None
    if deliver_to is not None:
        router, target = state.delivery_router, deliver_to

        async def _deliver(text: str) -> None:
            await router.deliver(target, text)
            # M278: record the answer in the chat's session (as M214 reminders
            # and M273 jobs are), so a reply has context — unless the run WAS
            # that session and already holds it. Compared at delivery time: the
            # factory may have re-allocated a stale session id meanwhile.
            run = started["handle"]
            slot = chat_session_slot(state, target)
            chat_session = slot[0].get(slot[1]) if slot else None
            if run.session_id is not None and run.session_id == chat_session:
                return
            try:
                from veles.daemon.background_ops import make_proactive_binder

                await make_proactive_binder(state)(target, text)
            except Exception as exc:  # binding never un-delivers the answer
                logger.warning("run %s post-deliver bind failed: %s", run.run_id, exc)

        deliver_hook = _deliver

    from veles.daemon.turns import start_turn

    try:
        handle = await start_turn(
            state,
            prompt=prompt,
            session_id=session_id,
            origin=origin,
            on_finished=_on_finished,
            deliver_hook=deliver_hook,
            mode=mode,
        )
    except Exception as exc:
        logger.error("failed to build agent for POST /v1/runs: %s: %s", type(exc).__name__, exc)
        return web.json_response(
            {"error": "failed to build agent", "detail": f"{type(exc).__name__}: {exc}"},
            status=500,
        )
    started["handle"] = handle
    logger.info(
        "POST /v1/runs run_id=%s session_id=%s prompt_len=%d",
        handle.run_id,
        session_id or "<new>",
        len(prompt),
    )
    return web.json_response(handle.to_summary(), status=202)


async def _handle_list_runs(request: web.Request) -> web.Response:
    state: DaemonState = request.app["state"]
    return web.json_response({"runs": [h.to_summary() for h in state.list_runs()]})


async def _handle_get_run(request: web.Request) -> web.Response:
    state: DaemonState = request.app["state"]
    run_id = request.match_info["run_id"]
    handle = state.get_run(run_id)
    if handle is None:
        return web.json_response({"error": f"run {run_id!r} not found"}, status=404)
    # M234: the answer text is served here and ONLY here. Until now it existed
    # solely in the WS `completed` event, so a caller that didn't want to hold a
    # WebSocket had no way to read its own result. It stays off the LIST endpoint
    # deliberately: `state.runs` is never pruned, so putting text in `to_summary`
    # would grow `GET /v1/runs` by every answer for the daemon's whole lifetime.
    return web.json_response(
        handle.to_summary()
        | {"final_text": handle.final_text, "delivery_error": handle.delivery_error}
    )


async def _handle_resolve_prompt(request: web.Request) -> web.Response:
    """Channel-supplied answer to a `trust_prompt` / `approval_prompt`.

    Body: `{"choice": "<key>"}` where `<key>` is one of the keys the
    daemon advertised in the matching event's `options` list (e.g.
    `"once"`, `"always_project"`, `"refuse"`, `"yes"`, `"no"`).

    Returns 200 on success, 404 if the run / prompt isn't registered
    (already resolved, already timed out, or never existed), 400 on a
    malformed body, 409 on an unknown choice key for that prompt's
    `kind`.
    """
    state: DaemonState = request.app["state"]
    run_id = request.match_info["run_id"]
    prompt_id = request.match_info["prompt_id"]
    handle = state.get_run(run_id)
    if handle is None:
        return web.json_response({"error": f"run {run_id!r} not found"}, status=404)
    body = await json_object(request)
    if isinstance(body, web.Response):
        return body
    choice = body.get("choice")
    if not isinstance(choice, str) or not choice:
        return web.json_response({"error": "'choice' (non-empty string) required"}, status=400)
    try:
        handle.resolve_prompt(prompt_id, choice)
    except LookupError as exc:
        return web.json_response({"error": str(exc)}, status=404)
    except ValueError as exc:
        # The prompt stays pending, so a follow-up POST with a valid key resolves it.
        valid = handle.pending_prompts[prompt_id].valid_choices
        return web.json_response({"error": str(exc), "valid_choices": list(valid)}, status=409)
    return web.json_response({"accepted": True, "choice": choice})


async def _handle_run_events_ws(request: web.Request) -> web.StreamResponse:
    state: DaemonState = request.app["state"]
    run_id = request.match_info["run_id"]
    handle = state.get_run(run_id)
    if handle is None:
        return web.json_response({"error": f"run {run_id!r} not found"}, status=404)

    ws = web.WebSocketResponse(heartbeat=15.0)
    await ws.prepare(request)

    try:
        async for event in handle.iter_events():
            await ws.send_json(event)
    except asyncio.CancelledError:
        pass
    finally:
        # Drain any client-side close message politely.
        async for msg in ws:
            if msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSING, WSMsgType.CLOSED):
                break
        await ws.close()
    return ws


async def _handle_list_sessions(request: web.Request) -> web.Response:
    state: DaemonState = request.app["state"]
    limit_raw = request.query.get("limit")
    try:
        limit = int(limit_raw) if limit_raw else 20
    except ValueError:
        return web.json_response({"error": "'limit' must be an integer"}, status=400)
    limit = max(1, min(limit, 200))
    sessions = state.store.list_sessions(limit=limit)
    return web.json_response(
        {
            "sessions": [
                {
                    "id": s.id,
                    "created_at": s.created_at,
                    "last_activity_at": s.last_activity_at,
                    "turn_count": s.turn_count,
                    "title": s.title,
                }
                for s in sessions
            ]
        }
    )


async def _handle_get_session(request: web.Request) -> web.Response:
    state: DaemonState = request.app["state"]
    session_id = request.match_info["session_id"]
    info = state.store.get_session(session_id)
    if info is None:
        return web.json_response({"error": f"session {session_id!r} not found"}, status=404)
    messages = state.store.load_messages(session_id)
    history: list[dict[str, Any]] = []
    for m in messages:
        history.append(
            {
                "role": m.role,
                "content": m.content,
                "tool_call_id": m.tool_call_id,
                "tool_calls": [
                    {"id": tc.id, "name": tc.name, "arguments": tc.arguments} for tc in m.tool_calls
                ]
                if m.tool_calls
                else [],
            }
        )
    return web.json_response(
        {
            "id": info.id,
            "created_at": info.created_at,
            "last_activity_at": info.last_activity_at,
            "turn_count": info.turn_count,
            "title": info.title,
            "messages": history,
            # M280: the session's agent mode (PATCH below); "default" = never switched.
            "mode": state.chat_mode(session_id).mode or "default",
            # M280b: the goal this chat is running (null when none), for `/goal`.
            "goal": state.chat_goal(session_id),
        }
    )


async def _handle_delete_session(request: web.Request) -> web.Response:
    state: DaemonState = request.app["state"]
    session_id = request.match_info["session_id"]
    deleted = state.store.delete_session(session_id)
    if not deleted:
        return web.json_response({"error": f"session {session_id!r} not found"}, status=404)
    return web.json_response({"deleted": True, "session_id": session_id})


async def _handle_cancel_session_goal(request: web.Request) -> web.Response:
    """DELETE /v1/sessions/{session_id}/goal — cancel the goal this chat runs
    (Telegram `/goal cancel`); the chat returns to its default mode. A drive in
    progress stops on its next turn. `cancelled` is null when there was none."""
    state: DaemonState = request.app["state"]
    session_id = request.match_info["session_id"]
    goal = state.cancel_chat_goal(session_id, reason="cancelled from the chat")
    return web.json_response({"session_id": session_id, "cancelled": goal})


async def _handle_patch_session(request: web.Request) -> web.Response:
    """PATCH /v1/sessions/{session_id} — set the session's agent mode.

    Body: `{"mode": str}`, one of `default`/auto/planning/writing/goal;
    `default` returns the chat to the plain single-agent turn. M280: the next
    turn of that session runs in this mode (`daemon/turns.py::start_turn`) —
    before M280 the value was stored and never read.

    `model` and `provider` are **fixed at daemon launch** from `config.toml`
    (`[engine]` / `[routing.tasks]`) — supplying either is a 400. The mode is
    the only per-session override.
    """
    state: DaemonState = request.app["state"]
    session_id = request.match_info["session_id"]
    body = await json_object(request)
    if isinstance(body, web.Response):
        return body

    # M127: model/provider are immutable after launch.
    if body.get("model", _SENTINEL) is not _SENTINEL or (
        body.get("provider", _SENTINEL) is not _SENTINEL
    ):
        return web.json_response(
            {
                "error": "model and provider are fixed at daemon launch; "
                "set them in config.toml ([engine] / [routing.tasks]) "
                "before starting the daemon"
            },
            status=400,
        )

    mode = body.get("mode", _SENTINEL)
    if mode is _SENTINEL:
        return web.json_response({"error": "mode required"}, status=400)
    if not isinstance(mode, str) or (mode != "default" and mode not in CHAT_MODES):
        return web.json_response(
            {
                "error": f"invalid mode {mode!r}",
                "valid_modes": ["default", *sorted(CHAT_MODES)],
            },
            status=400,
        )

    state.set_chat_mode(session_id, None if mode == "default" else mode)
    logger.info("PATCH /v1/sessions/%s mode=%s", session_id, mode)
    return web.json_response({"session_id": session_id, "mode": mode})


_SENTINEL = object()


async def _start_background_runners(app: web.Application) -> None:
    """Start JobRunner / DreamRunner / channel gateways if they're wired."""
    state: DaemonState = app["state"]
    for runner in (state.job_runner, state.dream_runner, state.reminder_runner):
        start_fn = getattr(runner, "start", None)
        if callable(start_fn):
            await start_fn()
    start_channel_runners(state)


async def _stop_background_runners(app: web.Application) -> None:
    state: DaemonState = app["state"]
    for runner in (state.job_runner, state.dream_runner, state.reminder_runner):
        if runner is None:
            continue
        stop_fn = getattr(runner, "stop", None)
        if callable(stop_fn):
            with contextlib.suppress(Exception):
                await stop_fn()
    for runner in state.channel_runners:
        stop_fn = getattr(runner, "stop", None)
        if callable(stop_fn):
            with contextlib.suppress(Exception):
                await stop_fn()
    for task in state.channel_tasks:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task
    state.channel_runners.clear()
    state.channel_tasks.clear()
    state.active_channels.clear()


async def _drain_in_flight_runs(app: web.Application) -> None:
    """Wait for every active run to finish so SQLite writes don't outlive the loop."""
    state: DaemonState = app["state"]
    for handle in state.list_runs():
        if handle.done.is_set():
            continue
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(handle.done.wait(), timeout=10.0)


def build_state(
    *,
    project,
    store,
    token_store: TokenStore,
    agent_factory: AgentFactory,
    provider: str | None = None,
    default_model: str | None = None,
    session_name: str | None = None,
) -> DaemonState:
    """Convenience constructor used by both CLI and tests.

    M127: the daemon's model/provider are fixed at launch from config and
    nothing about models is rehydrated from the store, so `/v1/health`
    `active_model` always reflects the configured model. Chat modes and their
    goals (M280/M282) ARE reloaded: a restart must not make a chat forget the
    goal it is running."""
    from veles.daemon.state import chat_modes_file, load_chat_modes

    path = chat_modes_file(project, session_name)
    return DaemonState(
        project=project,
        store=store,
        token_store=token_store,
        agent_factory=agent_factory,
        started_at=time.time(),
        provider=provider,
        default_model=default_model,
        session_name=session_name,
        chat_modes=load_chat_modes(path),
        chat_modes_path=path,
    )
