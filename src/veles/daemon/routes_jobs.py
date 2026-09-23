"""`/v1/jobs` (the scheduler) and `/v1/dream` (the dream runner) HTTP routes."""

from __future__ import annotations

import contextlib
from typing import Any

from aiohttp import web

from veles.daemon.http_util import json_object, runner_status
from veles.daemon.state import DaemonState


def add_job_routes(app: web.Application) -> None:
    app.router.add_post("/v1/jobs", _handle_create_job)
    app.router.add_get("/v1/jobs", _handle_list_jobs)
    app.router.add_get("/v1/jobs/{job_id}", _handle_get_job)
    app.router.add_patch("/v1/jobs/{job_id}", _handle_update_job)
    app.router.add_delete("/v1/jobs/{job_id}", _handle_delete_job)
    app.router.add_post("/v1/jobs/{job_id}/trigger", _handle_trigger_job)
    app.router.add_get("/v1/jobs/{job_id}/runs", _handle_list_job_runs)
    app.router.add_get("/v1/dream/status", _handle_dream_status)
    app.router.add_post("/v1/dream/run", _handle_dream_run)


def _jobs_store(request: web.Request) -> Any:
    runner = request.app["state"].job_runner
    return None if runner is None else getattr(runner, "_store", None)


def _jobs_store_or_503(request: web.Request) -> Any:
    """The scheduler's jobs store, or the 503 response when none is running."""
    store = _jobs_store(request)
    if store is None:
        return web.json_response({"error": "scheduler not enabled on this daemon"}, status=503)
    return store


async def _handle_create_job(request: web.Request) -> web.Response:
    store = _jobs_store_or_503(request)
    if isinstance(store, web.Response):
        return store
    body = await json_object(request)
    if isinstance(body, web.Response):
        return body
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
    return web.json_response(rec.to_dict(), status=201)


async def _handle_list_jobs(request: web.Request) -> web.Response:
    store = _jobs_store(request)
    if store is None:
        return web.json_response({"jobs": []})
    include_disabled = request.query.get("include_disabled", "1") != "0"
    return web.json_response(
        {"jobs": [r.to_dict() for r in store.list_jobs(include_disabled=include_disabled)]}
    )


async def _handle_get_job(request: web.Request) -> web.Response:
    store = _jobs_store_or_503(request)
    if isinstance(store, web.Response):
        return store
    rec = store.get_job(request.match_info["job_id"])
    if rec is None:
        return web.json_response({"error": "not found"}, status=404)
    return web.json_response(rec.to_dict())


async def _handle_update_job(request: web.Request) -> web.Response:
    store = _jobs_store_or_503(request)
    if isinstance(store, web.Response):
        return store
    body = await json_object(request)
    if isinstance(body, web.Response):
        return body
    try:
        ok = store.update_job(request.match_info["job_id"], **body)
    except ValueError as exc:
        return web.json_response({"error": str(exc)}, status=400)
    if not ok:
        return web.json_response({"error": "not found"}, status=404)
    rec = store.get_job(request.match_info["job_id"])
    return web.json_response(rec.to_dict())


async def _handle_delete_job(request: web.Request) -> web.Response:
    store = _jobs_store_or_503(request)
    if isinstance(store, web.Response):
        return store
    if not store.delete_job(request.match_info["job_id"]):
        return web.json_response({"error": "not found"}, status=404)
    return web.json_response({"deleted": True})


async def _handle_trigger_job(request: web.Request) -> web.Response:
    store = _jobs_store_or_503(request)
    if isinstance(store, web.Response):
        return store
    if not store.trigger_job(request.match_info["job_id"]):
        return web.json_response({"error": "not found"}, status=404)
    return web.json_response({"triggered": True})


async def _handle_list_job_runs(request: web.Request) -> web.Response:
    store = _jobs_store(request)
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


async def _handle_dream_status(request: web.Request) -> web.Response:
    state: DaemonState = request.app["state"]
    return web.json_response(runner_status(state.dream_runner) or {"enabled": False})


async def _handle_dream_run(request: web.Request) -> web.Response:
    state: DaemonState = request.app["state"]
    if state.dream_runner is None:
        return web.json_response({"error": "dream-runner not enabled"}, status=503)
    body: Any = {}
    with contextlib.suppress(Exception):
        body = await request.json()
    if not isinstance(body, dict):  # a JSON array/number body is not an error-500
        body = {}
    include_consolidation = bool(body.get("include_consolidation", True))
    force_fn = getattr(state.dream_runner, "force_run", None)
    if not callable(force_fn):
        return web.json_response({"error": "dream-runner missing force_run"}, status=500)
    result = await force_fn(include_consolidation=include_consolidation)
    return web.json_response({"summary": result.summary(), "notes": result.notes})
