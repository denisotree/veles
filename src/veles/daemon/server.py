"""Daemon HTTP + WebSocket server (M51).

aiohttp app exposing six endpoints under `/v1/`:

    GET  /v1/health                           → unauth, status probe
    POST /v1/runs                             → submit a prompt → run_id
    GET  /v1/runs                             → list run summaries
    GET  /v1/runs/{run_id}                    → single run summary
    WS   /v1/runs/{run_id}/events             → stream events
    GET  /v1/sessions                         → list sessions
    GET  /v1/sessions/{id}                    → session detail (history)
    DELETE /v1/sessions/{id}                  → delete a session

Every endpoint except `/v1/health` is gated by
`bearer_auth_middleware`. The token store is reloaded on every request
so out-of-band token CRUD propagates without a restart.

The app accepts an `AgentFactory` callable so tests can inject stub
providers without touching the network. Production CLI wires the
factory to construct an `Agent` via the existing `_make_provider` +
runtime helpers — see `cli/commands/daemon.py`.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from typing import Any

from aiohttp import WSMsgType, web

from veles import __version__
from veles.daemon.auth import TokenStore, bearer_auth_middleware
from veles.daemon.runner import (
    AgentFactory,
    new_run_handle,
    run_agent_in_background,
    run_manager_in_background,
)
from veles.daemon.state import DaemonState

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
    # M75 jobs API
    app.router.add_post("/v1/jobs", _handle_create_job)
    app.router.add_get("/v1/jobs", _handle_list_jobs)
    app.router.add_get("/v1/jobs/{job_id}", _handle_get_job)
    app.router.add_patch("/v1/jobs/{job_id}", _handle_update_job)
    app.router.add_delete("/v1/jobs/{job_id}", _handle_delete_job)
    app.router.add_post("/v1/jobs/{job_id}/trigger", _handle_trigger_job)
    app.router.add_get("/v1/jobs/{job_id}/runs", _handle_list_job_runs)
    # M76 dream API
    app.router.add_get("/v1/dream/status", _handle_dream_status)
    app.router.add_post("/v1/dream/run", _handle_dream_run)
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
    job_status = None
    if state.job_runner is not None:
        # Best-effort: any concrete JobRunner that exposes `status()` wins;
        # otherwise we report just `enabled`.
        status_fn = getattr(state.job_runner, "status", None)
        job_status = status_fn() if callable(status_fn) else {"enabled": True}
    dream_status = None
    if state.dream_runner is not None:
        status_fn = getattr(state.dream_runner, "status", None)
        dream_status = status_fn() if callable(status_fn) else {"enabled": True}
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
            "jobs": job_status,
            "dream": dream_status,
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
        _default_channels_dir,
        channel_session_path,
    )

    ensure_builtins_registered()
    platforms = list_platforms()
    channels_dir = _default_channels_dir()
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


async def _handle_create_run(request: web.Request) -> web.Response:
    state: DaemonState = request.app["state"]
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        return web.json_response({"error": "body must be JSON"}, status=400)
    if not isinstance(body, dict):
        return web.json_response({"error": "body must be a JSON object"}, status=400)
    prompt = body.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return web.json_response({"error": "'prompt' (non-empty string) required"}, status=400)
    session_id = body.get("session_id")
    if session_id is not None and not isinstance(session_id, str):
        return web.json_response({"error": "'session_id' must be a string"}, status=400)

    handle = new_run_handle(session_id=session_id)
    state.add_run(handle)
    logger.info(
        "POST /v1/runs run_id=%s session_id=%s prompt_len=%d",
        handle.run_id,
        session_id or "<new>",
        len(prompt),
    )

    def _on_finished(_: Any) -> None:
        state.touch_activity()

    # M124: route long / research-keyword prompts through the manager-
    # spawn orchestrator. Worker factory is per-daemon (built in
    # `_make_worker_agent_factory`); when absent (older callers /
    # tests), skip silently and fall through to the direct path.
    if state.worker_agent_factory is not None and _should_use_manager_safe(prompt):
        task = asyncio.create_task(
            run_manager_in_background(
                handle,
                worker_agent_factory=state.worker_agent_factory,
                prompt=prompt,
                on_finished=_on_finished,
            )
        )
        state.run_tasks.add(task)
        task.add_done_callback(state.run_tasks.discard)
        return web.json_response(handle.to_summary(), status=202)

    try:
        agent = state.agent_factory(session_id, prompt=prompt)
    except Exception as exc:
        handle.state = "failed"
        handle.error = f"{type(exc).__name__}: {exc}"
        handle.finished_at = time.time()
        logger.error(
            "failed to build agent for run_id=%s: %s: %s",
            handle.run_id,
            type(exc).__name__,
            exc,
        )
        return web.json_response(
            {"error": "failed to build agent", "detail": handle.error},
            status=500,
        )

    task = asyncio.create_task(
        run_agent_in_background(
            handle,
            agent=agent,
            prompt=prompt,
            on_finished=_on_finished,
            post_turn_hook=state.post_turn_hook,
        )
    )
    state.run_tasks.add(task)
    task.add_done_callback(state.run_tasks.discard)
    return web.json_response(handle.to_summary(), status=202)


def _should_use_manager_safe(prompt: str) -> bool:
    """Resolve the manager gate without crashing the daemon if the
    orchestration module isn't importable (defensive — should always
    be present in normal installs).

    M122f: opt-in, default OFF — the daemon routes through the manager only
    when `VELES_MANAGER_MODE=1` is set in its environment (the auto-heuristic
    is disabled so background/channel turns don't silently fan out to N
    sub-agents)."""
    try:
        from veles.core.orchestration import should_use_manager

        return should_use_manager(prompt, use_heuristic_default=False)
    except Exception:
        return False


async def _handle_list_runs(request: web.Request) -> web.Response:
    state: DaemonState = request.app["state"]
    return web.json_response({"runs": [h.to_summary() for h in state.list_runs()]})


async def _handle_get_run(request: web.Request) -> web.Response:
    state: DaemonState = request.app["state"]
    run_id = request.match_info["run_id"]
    handle = state.get_run(run_id)
    if handle is None:
        return web.json_response({"error": f"run {run_id!r} not found"}, status=404)
    return web.json_response(handle.to_summary())


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
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        return web.json_response({"error": "body must be JSON"}, status=400)
    if not isinstance(body, dict):
        return web.json_response({"error": "body must be a JSON object"}, status=400)
    choice = body.get("choice")
    if not isinstance(choice, str) or not choice:
        return web.json_response({"error": "'choice' (non-empty string) required"}, status=400)
    pending = handle.pending_prompts.pop(prompt_id, None)
    if pending is None:
        return web.json_response({"error": f"prompt {prompt_id!r} not pending"}, status=404)
    if choice not in pending.valid_choices:
        # Put it back so a follow-up POST with the right key can still resolve.
        handle.pending_prompts[prompt_id] = pending
        return web.json_response(
            {
                "error": f"choice {choice!r} not valid for {pending.kind} prompt",
                "valid_choices": list(pending.valid_choices),
            },
            status=409,
        )
    pending.future.set_result(choice)
    handle.append_event({"type": "prompt_resolved", "prompt_id": prompt_id, "choice": choice})
    return web.json_response({"accepted": True, "choice": choice})


async def _handle_run_events_ws(request: web.Request) -> web.StreamResponse:
    state: DaemonState = request.app["state"]
    run_id = request.match_info["run_id"]
    handle = state.get_run(run_id)
    if handle is None:
        return web.json_response({"error": f"run {run_id!r} not found"}, status=404)

    ws = web.WebSocketResponse(heartbeat=15.0)
    await ws.prepare(request)

    cursor = 0
    try:
        while True:
            while cursor < len(handle.events):
                event = handle.events[cursor]
                cursor += 1
                await ws.send_json(event)
            if handle.done.is_set() and cursor >= len(handle.events):
                break
            try:
                await asyncio.wait_for(handle.event_added.wait(), timeout=30.0)
            except TimeoutError:
                if handle.done.is_set() and cursor >= len(handle.events):
                    break
                continue
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
    # M126 observability: surface the per-session overrides set via
    # PATCH /v1/sessions/{id}. Empty/absent override → `null` so callers
    # can tell "no override" from "override cleared to default".
    overrides = state.get_overrides(session_id)
    overrides_payload: dict[str, Any] | None
    overrides_payload = None if overrides is None or overrides.is_empty() else overrides.to_dict()
    return web.json_response(
        {
            "id": info.id,
            "created_at": info.created_at,
            "last_activity_at": info.last_activity_at,
            "turn_count": info.turn_count,
            "title": info.title,
            "messages": history,
            "overrides": overrides_payload,
        }
    )


async def _handle_delete_session(request: web.Request) -> web.Response:
    state: DaemonState = request.app["state"]
    session_id = request.match_info["session_id"]
    deleted = state.store.delete_session(session_id)
    if not deleted:
        return web.json_response({"error": f"session {session_id!r} not found"}, status=404)
    return web.json_response({"deleted": True, "session_id": session_id})


# M126: per-session config overrides — used by channels (Telegram
# inline keyboards) so users can switch model/mode mid-conversation
# without going through TUI or restarting the daemon.
_VALID_MODES_PATCH = frozenset({"auto", "planning", "writing", "goal"})


async def _handle_patch_session(request: web.Request) -> web.Response:
    """PATCH /v1/sessions/{session_id} — set the per-session `mode`.

    Body: `{"mode": str}` where mode is one of auto/planning/writing/goal.

    M127: `model` and `provider` are **fixed at daemon launch** from
    `config.toml` (`[provider]` / `[routing.tasks]`) and can no longer be
    changed per-session — supplying either is a 400. The Telegram `/model`
    picker was removed; `/mode` is the only remaining per-session override.
    """
    state: DaemonState = request.app["state"]
    session_id = request.match_info["session_id"]
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        return web.json_response({"error": "body must be JSON"}, status=400)
    if not isinstance(body, dict):
        return web.json_response({"error": "body must be a JSON object"}, status=400)

    # M127: model/provider are immutable after launch.
    if body.get("model", _SENTINEL) is not _SENTINEL or (
        body.get("provider", _SENTINEL) is not _SENTINEL
    ):
        return web.json_response(
            {
                "error": "model and provider are fixed at daemon launch; "
                "set them in config.toml ([provider] / [routing.tasks]) "
                "before starting the daemon"
            },
            status=400,
        )

    mode = body.get("mode", _SENTINEL)
    if mode is _SENTINEL:
        return web.json_response({"error": "mode required"}, status=400)
    if mode is not None and (not isinstance(mode, str) or mode not in _VALID_MODES_PATCH):
        return web.json_response(
            {
                "error": f"invalid mode {mode!r}",
                "valid_modes": sorted(_VALID_MODES_PATCH),
            },
            status=400,
        )

    overrides = state.set_overrides(session_id, mode=mode)
    logger.info("PATCH /v1/sessions/%s overrides=%s", session_id, overrides.to_dict())
    return web.json_response({"session_id": session_id, "overrides": overrides.to_dict()})


_SENTINEL = object()


# ---- jobs handlers (M75) ----


def _require_jobs_store(state: DaemonState):
    jr = state.job_runner
    if jr is None:
        return None
    return getattr(jr, "_store", None)


def _job_to_dict(rec) -> dict[str, Any]:
    return {
        "id": rec.id,
        "name": rec.name,
        "prompt": rec.prompt,
        "schedule": {
            "kind": rec.schedule.kind,
            "expr": rec.schedule.expr,
            "display": rec.schedule.display(),
        },
        "repeat_times": rec.repeat_times,
        "repeat_completed": rec.repeat_completed,
        "context_from": rec.context_from,
        "deliver_to": rec.deliver_to,
        "enabled": rec.enabled,
        "state": rec.state,
        "created_at": rec.created_at,
        "next_run_at": rec.next_run_at,
        "last_run_at": rec.last_run_at,
        "last_status": rec.last_status,
        "last_error": rec.last_error,
        "last_output_path": rec.last_output_path,
    }


async def _handle_create_job(request: web.Request) -> web.Response:
    state: DaemonState = request.app["state"]
    store = _require_jobs_store(state)
    if store is None:
        return web.json_response({"error": "scheduler not enabled on this daemon"}, status=503)
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        return web.json_response({"error": "body must be JSON"}, status=400)
    if not isinstance(body, dict):
        return web.json_response({"error": "body must be a JSON object"}, status=400)
    try:
        rec = store.add_job(
            name=str(body.get("name") or ""),
            prompt=str(body.get("prompt") or ""),
            schedule_expr=str(body.get("schedule") or ""),
            repeat_times=body.get("repeat_times"),
            context_from=body.get("context_from"),
            deliver_to=body.get("deliver_to"),
            enabled=bool(body.get("enabled", True)),
        )
    except ValueError as exc:
        return web.json_response({"error": str(exc)}, status=400)
    return web.json_response(_job_to_dict(rec), status=201)


async def _handle_list_jobs(request: web.Request) -> web.Response:
    state: DaemonState = request.app["state"]
    store = _require_jobs_store(state)
    if store is None:
        return web.json_response({"jobs": []})
    include_disabled = request.query.get("include_disabled", "1") != "0"
    return web.json_response(
        {"jobs": [_job_to_dict(r) for r in store.list_jobs(include_disabled=include_disabled)]}
    )


async def _handle_get_job(request: web.Request) -> web.Response:
    state: DaemonState = request.app["state"]
    store = _require_jobs_store(state)
    if store is None:
        return web.json_response({"error": "scheduler not enabled"}, status=503)
    rec = store.get_job(request.match_info["job_id"])
    if rec is None:
        return web.json_response({"error": "not found"}, status=404)
    return web.json_response(_job_to_dict(rec))


async def _handle_update_job(request: web.Request) -> web.Response:
    state: DaemonState = request.app["state"]
    store = _require_jobs_store(state)
    if store is None:
        return web.json_response({"error": "scheduler not enabled"}, status=503)
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        return web.json_response({"error": "body must be JSON"}, status=400)
    if not isinstance(body, dict):
        return web.json_response({"error": "body must be a JSON object"}, status=400)
    try:
        ok = store.update_job(request.match_info["job_id"], **body)
    except ValueError as exc:
        return web.json_response({"error": str(exc)}, status=400)
    if not ok:
        return web.json_response({"error": "not found"}, status=404)
    rec = store.get_job(request.match_info["job_id"])
    return web.json_response(_job_to_dict(rec))


async def _handle_delete_job(request: web.Request) -> web.Response:
    state: DaemonState = request.app["state"]
    store = _require_jobs_store(state)
    if store is None:
        return web.json_response({"error": "scheduler not enabled"}, status=503)
    if not store.delete_job(request.match_info["job_id"]):
        return web.json_response({"error": "not found"}, status=404)
    return web.json_response({"deleted": True})


async def _handle_trigger_job(request: web.Request) -> web.Response:
    state: DaemonState = request.app["state"]
    store = _require_jobs_store(state)
    if store is None:
        return web.json_response({"error": "scheduler not enabled"}, status=503)
    if not store.trigger_job(request.match_info["job_id"]):
        return web.json_response({"error": "not found"}, status=404)
    return web.json_response({"triggered": True})


async def _handle_list_job_runs(request: web.Request) -> web.Response:
    state: DaemonState = request.app["state"]
    store = _require_jobs_store(state)
    if store is None:
        return web.json_response({"runs": []})
    limit_raw = request.query.get("limit", "20")
    try:
        limit = max(1, min(int(limit_raw), 200))
    except ValueError:
        return web.json_response({"error": "'limit' must be an integer"}, status=400)
    runs = store.list_runs(request.match_info["job_id"], limit=limit)
    return web.json_response(
        {
            "runs": [
                {
                    "run_id": r.run_id,
                    "job_id": r.job_id,
                    "started_at": r.started_at,
                    "finished_at": r.finished_at,
                    "status": r.status,
                    "iterations": r.iterations,
                    "output_path": r.output_path,
                    "error": r.error,
                }
                for r in runs
            ]
        }
    )


# ---- dream handlers (M76) ----


async def _handle_dream_status(request: web.Request) -> web.Response:
    state: DaemonState = request.app["state"]
    if state.dream_runner is None:
        return web.json_response({"enabled": False})
    status_fn = getattr(state.dream_runner, "status", None)
    if callable(status_fn):
        return web.json_response(status_fn())
    return web.json_response({"enabled": True})


async def _handle_dream_run(request: web.Request) -> web.Response:
    state: DaemonState = request.app["state"]
    if state.dream_runner is None:
        return web.json_response({"error": "dream-runner not enabled"}, status=503)
    body: dict[str, Any] = {}
    with contextlib.suppress(Exception):
        body = await request.json()
    include_consolidation = bool(body.get("include_consolidation", True))
    force_fn = getattr(state.dream_runner, "force_run", None)
    if not callable(force_fn):
        return web.json_response({"error": "dream-runner missing force_run"}, status=500)
    result = await force_fn(include_consolidation=include_consolidation)
    return web.json_response({"summary": result.summary(), "notes": result.notes})


async def _start_background_runners(app: web.Application) -> None:
    """Start JobRunner / DreamRunner / channel gateways if they're wired."""
    state: DaemonState = app["state"]
    if state.job_runner is not None:
        start_fn = getattr(state.job_runner, "start", None)
        if callable(start_fn):
            await start_fn()
    if state.dream_runner is not None:
        start_fn = getattr(state.dream_runner, "start", None)
        if callable(start_fn):
            await start_fn()
    _start_channel_runners(state)


async def _stop_background_runners(app: web.Application) -> None:
    state: DaemonState = app["state"]
    for runner in (state.job_runner, state.dream_runner):
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


def _channel_session_map(state: DaemonState, platform: str):
    """Per-(session, platform) chat→session map so two daemon sessions running
    the same platform keep independent conversation contexts. The unnamed
    daemon keeps the back-compat `<platform>-sessions.json` key."""
    from veles.channels.session_map import SessionMap, channel_session_path

    key = f"{state.session_name}-{platform}" if state.session_name else platform
    return SessionMap.load(channel_session_path(key))


def _build_channel_gateway(platform: str, channel_cfg: dict, *, backend, state: DaemonState):
    """Resolve creds + build one gateway via the platform registry. Returns
    None (and warns) when the platform is unregistered or its token is
    missing — a bad channel is skipped, never fatal to daemon startup."""
    from veles.channels.platform_registry import get_platform
    from veles.core.secrets import get_provider_key

    try:
        entry = get_platform(platform)
    except KeyError:
        logger.warning("channel %r is not a registered platform — skipping", platform)
        return None
    token = get_provider_key(platform, project=state.project.name) or channel_cfg.get("bot_token")
    if not token:
        logger.warning(
            "[channels.%s] enabled but no bot token in keychain (veles:%s:%s) or config — skipping",
            platform,
            platform,
            state.project.name,
        )
        return None
    session_map = _channel_session_map(state, platform)
    if platform == "telegram":
        raw_whitelist = channel_cfg.get("whitelist") or []
        if isinstance(raw_whitelist, str):
            raw_whitelist = [raw_whitelist]
        whitelist = tuple(str(x) for x in raw_whitelist if str(x).strip())
        # Stdin-fallback wizard wrote chat_id as a single allowed peer; honor it.
        legacy_chat_id = channel_cfg.get("chat_id")
        if legacy_chat_id and not whitelist:
            whitelist = (str(legacy_chat_id),)
        gateway = entry.factory(
            bot_token=str(token),
            daemon_client=backend,
            session_map=session_map,
            whitelist=whitelist,
            attachment_dir=state.project.tmp_dir,
            project_root=state.project.root,
        )
        logger.info("telegram channel started (whitelist: %d entries)", len(whitelist))
        return gateway
    # Generic platforms use the minimal factory contract shared with
    # `veles channel run` (bot_token / daemon_client / session_map).
    gateway = entry.factory(bot_token=str(token), daemon_client=backend, session_map=session_map)
    logger.info("channel %r started", platform)
    return gateway


def _start_channel_runners(state: DaemonState) -> None:
    """Read declared channels from config and start in-process gateways.

    Generic over platforms (`channels/platform_registry`) and over several
    channels per daemon. For a named session (`state.session_name`) the source
    is `[daemon.<name>.channels.<type>]`; otherwise the legacy global
    `[channels.<type>]`. Each enabled channel is resolved via the registry and
    given its own `SessionMap`; the run backend is `InProcessRunBackend` so no
    HTTP loopback / token is needed. Channels with missing creds (or an
    unregistered platform) are skipped with a warning rather than failing
    daemon startup.
    """
    from veles.channels.in_process_backend import InProcessRunBackend
    from veles.channels.platform_registry import ensure_builtins_registered
    from veles.core.project_config import list_channel_configs, load_project_config

    ensure_builtins_registered()
    cfg = load_project_config(state.project)
    declared = list_channel_configs(cfg, daemon_session=state.session_name)
    if not declared:
        return
    backend = InProcessRunBackend(state)
    for platform, channel_cfg in declared:
        gateway = _build_channel_gateway(platform, channel_cfg, backend=backend, state=state)
        if gateway is None:
            continue
        state.channel_runners.append(gateway)
        state.active_channels.append(platform)
        task = asyncio.create_task(_run_channel_gateway(gateway))
        state.channel_tasks.append(task)


async def _run_channel_gateway(gateway) -> None:
    """Wrap `gateway.start()` so a crash doesn't take down the daemon."""
    try:
        await gateway.start()
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.error("channel gateway crashed: %s: %s", type(exc).__name__, exc)
        with contextlib.suppress(Exception):
            await gateway.stop()


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

    M127: the daemon's model/provider are fixed at launch from config, so
    `session_overrides` starts empty and is NOT rehydrated from the store
    (the per-session `session_model_overrides` table was removed). This is
    what makes `/v1/health` `active_model` always reflect the configured
    model instead of resurrecting a stale Telegram `/model` choice."""
    return DaemonState(
        project=project,
        store=store,
        token_store=token_store,
        agent_factory=agent_factory,
        started_at=time.time(),
        provider=provider,
        default_model=default_model,
        session_name=session_name,
    )
