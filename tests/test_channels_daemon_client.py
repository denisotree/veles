"""M52 channels — DaemonClient against a stub aiohttp server.

Spins up a minimal aiohttp app that mimics the M51 daemon's
`/v1/health`, `/v1/runs`, `/v1/runs/{id}`, and
`WS /v1/runs/{id}/events` endpoints. Exercises auth-header propagation,
JSON parsing, error surface, and WebSocket event streaming.
"""

from __future__ import annotations

import pytest
from aiohttp import web

from veles.channels.daemon_client import DaemonClient, DaemonClientError

_VALID_TOKEN = "vd_abc123"


def _check_auth(request: web.Request) -> web.Response | None:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return web.json_response({"error": "missing"}, status=401)
    if auth[len("Bearer ") :] != _VALID_TOKEN:
        return web.json_response({"error": "invalid"}, status=401)
    return None


async def _health(_request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "project": "demo"})


async def _post_run(request: web.Request) -> web.Response:
    err = _check_auth(request)
    if err is not None:
        return err
    body = await request.json()
    return web.json_response(
        {
            "run_id": "run-test-1",
            "session_id": body.get("session_id"),
            "state": "running",
        },
        status=202,
    )


async def _get_run(request: web.Request) -> web.Response:
    err = _check_auth(request)
    if err is not None:
        return err
    return web.json_response(
        {
            "run_id": request.match_info["run_id"],
            "state": "completed",
            "stopped_reason": "completed",
        }
    )


async def _ws_events(request: web.Request) -> web.WebSocketResponse:
    err = _check_auth(request)
    if err is not None:
        # Reject WS before upgrade; aiohttp test client surfaces this as 401.
        return web.json_response({"error": "auth"}, status=401)
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    await ws.send_json({"type": "started", "run_id": request.match_info["run_id"]})
    await ws.send_json({"type": "text_delta", "delta": "hello "})
    await ws.send_json({"type": "text_delta", "delta": "world"})
    await ws.send_json({"type": "completed", "text": "hello world", "session_id": "ses-1"})
    await ws.close()
    return ws


@pytest.fixture()
def stub_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/v1/health", _health)
    app.router.add_post("/v1/runs", _post_run)
    app.router.add_get("/v1/runs/{run_id}", _get_run)
    app.router.add_get("/v1/runs/{run_id}/events", _ws_events)
    return app


async def _make_client(aiohttp_client, app, token: str = _VALID_TOKEN) -> DaemonClient:
    raw = await aiohttp_client(app)
    base = str(raw.make_url("")).rstrip("/")
    return DaemonClient(base, token, session=raw.session)


# ---- tests ----


async def test_health_returns_payload(aiohttp_client, stub_app) -> None:
    client = await _make_client(aiohttp_client, stub_app)
    body = await client.health()
    assert body["status"] == "ok"
    assert body["project"] == "demo"


async def test_submit_run_forwards_session_id_and_prompt(aiohttp_client, stub_app) -> None:
    client = await _make_client(aiohttp_client, stub_app)
    body = await client.submit_run("hi there", session_id="ses-X")
    assert body["run_id"] == "run-test-1"
    assert body["session_id"] == "ses-X"


async def test_submit_run_without_session_id(aiohttp_client, stub_app) -> None:
    client = await _make_client(aiohttp_client, stub_app)
    body = await client.submit_run("hello")
    assert body["run_id"] == "run-test-1"
    assert body["session_id"] is None


async def test_submit_run_raises_on_401(aiohttp_client, stub_app) -> None:
    client = await _make_client(aiohttp_client, stub_app, token="vd_wrong")
    with pytest.raises(DaemonClientError) as info:
        await client.submit_run("hi")
    assert info.value.status == 401


async def test_get_run_returns_summary(aiohttp_client, stub_app) -> None:
    client = await _make_client(aiohttp_client, stub_app)
    body = await client.get_run("run-test-1")
    assert body["state"] == "completed"
    assert body["stopped_reason"] == "completed"


async def test_stream_events_yields_until_completed(aiohttp_client, stub_app) -> None:
    client = await _make_client(aiohttp_client, stub_app)
    events = []
    async for event in client.stream_events("run-test-1"):
        events.append(event)
    types = [e["type"] for e in events]
    assert types == ["started", "text_delta", "text_delta", "completed"]
    deltas = [e["delta"] for e in events if e["type"] == "text_delta"]
    assert "".join(deltas) == "hello world"


async def test_health_works_without_token(aiohttp_client, stub_app) -> None:
    """The /v1/health endpoint doesn't enforce auth — client should still succeed."""
    client = await _make_client(aiohttp_client, stub_app, token="anything")
    body = await client.health()
    assert body["status"] == "ok"


async def test_daemon_client_error_carries_status_and_body() -> None:
    err = DaemonClientError("nope", status=503, body="upstream down")
    assert err.status == 503
    assert err.body == "upstream down"
    assert str(err) == "nope"


def test_daemon_client_outside_context_raises() -> None:
    client = DaemonClient("http://x", "vd_y")
    with pytest.raises(RuntimeError, match="async with"):
        _ = client.session


async def test_submit_run_handles_non_json_response(
    aiohttp_client,
) -> None:
    app = web.Application()

    async def bad_post(_request):
        return web.Response(text="<<not json>>", status=200)

    app.router.add_post("/v1/runs", bad_post)
    client = await _make_client(aiohttp_client, app)
    with pytest.raises(DaemonClientError, match="non-JSON"):
        await client.submit_run("x")
