"""Contracts the daemon must keep while its HTTP server and run plumbing are
reorganised: every route but health is authenticated, the HTTP event stream and
the in-process backend deliver the same events, and a reader that goes away
mid-run does not stop the run."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path

from aiohttp import WSMsgType

from veles.core.agent import RunResult
from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.daemon.auth import TokenStore
from veles.daemon.server import build_state, make_app

_OPEN_ROUTES = {"/v1/health"}


class _Agent:
    """Streams two deltas and finishes; `gate`, when given, holds the finish."""

    def __init__(self, gate: threading.Event | None = None) -> None:
        self._gate = gate

    def run(self, prompt, *, on_text_delta, event_listener=None):
        on_text_delta("he")
        on_text_delta("llo")
        if self._gate is not None:
            self._gate.wait(timeout=5)
        return RunResult(text="hello", iterations=1, stopped_reason="completed", session_id="s1")


def _state(tmp_path: Path, agent_factory):
    project = init_project(tmp_path / "p", name="p")
    tokens = TokenStore.load(tmp_path / "tokens.json")
    tokens.add("t")
    return build_state(
        project=project,
        store=SessionStore(project.memory_db_path),
        token_store=tokens,
        agent_factory=agent_factory,
    ), tokens.list()[0].token


async def test_every_route_but_health_requires_a_token(aiohttp_client, tmp_path) -> None:
    state, _token = _state(tmp_path, lambda sid, *, prompt=None: _Agent())
    app = make_app(state)
    client = await aiohttp_client(app)
    checked = 0
    for route in app.router.routes():
        path = route.resource.canonical if route.resource is not None else ""
        if route.method == "HEAD" or path in _OPEN_ROUTES:
            continue
        url = path.replace("{run_id}", "r").replace("{prompt_id}", "p")
        url = url.replace("{session_id}", "s").replace("{job_id}", "j")
        resp = await client.request(route.method, url)
        assert resp.status == 401, f"{route.method} {path} answered {resp.status} without a token"
        checked += 1
    assert checked >= 20  # the sweep really walked the API


def _types(events: list[dict]) -> list[str]:
    return [e["type"] for e in events]


async def test_http_stream_and_in_process_backend_deliver_the_same_events(
    aiohttp_client, tmp_path
) -> None:
    from veles.channels.in_process_backend import InProcessRunBackend

    state, token = _state(tmp_path, lambda sid, *, prompt=None: _Agent())
    client = await aiohttp_client(make_app(state))
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post("/v1/runs", json={"prompt": "hi"}, headers=headers)
    run_id = (await resp.json())["run_id"]
    http_events: list[dict] = []
    async with client.ws_connect(f"/v1/runs/{run_id}/events", headers=headers) as ws:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                break
            http_events.append(msg.json())
            if http_events[-1]["type"] in ("completed", "error"):
                break

    backend = InProcessRunBackend(state)
    submitted = await backend.submit_run("hi")
    local_events = [e async for e in backend.stream_events(submitted["run_id"])]

    assert _types(http_events) == _types(local_events)
    assert _types(local_events)[0] == "started"
    assert _types(local_events)[-1] == "completed"
    assert http_events[-1]["text"] == local_events[-1]["text"] == "hello"


async def test_a_reader_leaving_mid_run_does_not_stop_the_run(tmp_path) -> None:
    from veles.channels.in_process_backend import InProcessRunBackend

    gate = threading.Event()
    state, _token = _state(tmp_path, lambda sid, *, prompt=None: _Agent(gate))
    backend = InProcessRunBackend(state)
    submitted = await backend.submit_run("hi")

    stream = backend.stream_events(submitted["run_id"])
    first = await asyncio.wait_for(anext(stream), timeout=5)
    assert first["type"] == "started"
    await asyncio.wait_for(stream.aclose(), timeout=5)  # the reader goes away

    gate.set()
    handle = state.get_run(submitted["run_id"])
    assert handle is not None
    await asyncio.wait_for(handle.done.wait(), timeout=5)
    assert handle.state == "completed"
    assert handle.final_text == "hello"


async def test_a_websocket_closed_mid_run_does_not_stop_the_run(aiohttp_client, tmp_path) -> None:
    gate = threading.Event()
    state, token = _state(tmp_path, lambda sid, *, prompt=None: _Agent(gate))
    client = await aiohttp_client(make_app(state))
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post("/v1/runs", json={"prompt": "hi"}, headers=headers)
    run_id = (await resp.json())["run_id"]

    ws = await client.ws_connect(f"/v1/runs/{run_id}/events", headers=headers)
    msg = await asyncio.wait_for(ws.receive(), timeout=5)
    assert msg.json()["type"] == "started"
    # The server answers the close only between events, so close concurrently.
    closing = asyncio.create_task(ws.close())
    await asyncio.sleep(0.05)
    gate.set()
    handle = state.get_run(run_id)
    assert handle is not None
    await asyncio.wait_for(handle.done.wait(), timeout=5)
    await asyncio.wait_for(closing, timeout=5)
    assert handle.state == "completed"
