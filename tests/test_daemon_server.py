"""M51 daemon — HTTP + WebSocket endpoint tests.

Spins up the aiohttp app under `pytest-aiohttp`'s `aiohttp_client`
fixture, with an injected stub `AgentFactory` that yields scripted
streaming text without touching the network.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest
from aiohttp import WSMsgType, web

from tests.conftest import StubProvider
from veles.core.memory import SessionStore
from veles.core.project import Project, init_project
from veles.core.provider import (
    Message,
    ProviderResponse,
    StreamEnd,
    TextDelta,
    TokenUsage,
)
from veles.core.tools.registry import Registry
from veles.daemon.auth import TokenStore
from veles.daemon.runner import AgentFactory
from veles.daemon.server import build_state, make_app

# ---- stub provider + agent factory ----


def _stub_provider(chunks: list[str] | None = None) -> StubProvider:
    chunks = chunks or ["hello ", "world"]
    resp = ProviderResponse(
        text="".join(chunks),
        tool_calls=[],
        usage=TokenUsage(prompt_tokens=1, completion_tokens=2, total_tokens=3),
        finish_reason="stop",
    )
    return StubProvider(
        [resp],
        supports_tools=False,
        supports_streaming=True,
        stream_events=[TextDelta(text=ch) for ch in chunks] + [StreamEnd(response=resp)],
        repeat_last=True,
    )


def _make_stub_factory(store: SessionStore, *, chunks: list[str] | None = None) -> AgentFactory:
    from veles.core.agent import Agent

    def factory(session_id: str | None, *, prompt: str | None = None):
        sid = session_id or store.create_session()
        return Agent(
            provider=_stub_provider(chunks=chunks),
            registry=Registry(),
            model="stub-model",
            max_iterations=1,
            store=store,
            session_id=sid,
        )

    return factory


# ---- fixtures ----


@pytest.fixture()
def project(tmp_path: Path) -> Project:
    return init_project(tmp_path, name="dtest")


@pytest.fixture()
def store(project: Project):
    s = SessionStore(project.memory_db_path)
    # Don't close here — the aiohttp app's on_shutdown drains in-flight runs,
    # but the fixture order can still race the worker thread. Let the process
    # exit close the SQLite connection naturally.
    yield s


@pytest.fixture()
def token_store(tmp_path: Path) -> TokenStore:
    ts = TokenStore.load(tmp_path / "daemon.tokens.json")
    ts.add("default")
    return ts


@pytest.fixture()
def good_token(token_store: TokenStore) -> str:
    return token_store.list()[0].token


@pytest.fixture()
def app(project: Project, store: SessionStore, token_store: TokenStore) -> web.Application:
    factory = _make_stub_factory(store)
    state = build_state(
        project=project,
        store=store,
        token_store=token_store,
        agent_factory=factory,
    )
    return make_app(state)


# ---- /v1/health ----


async def test_health_returns_project_info(aiohttp_client, app) -> None:
    client = await aiohttp_client(app)
    resp = await client.get("/v1/health")
    assert resp.status == 200
    body = await resp.json()
    assert body["status"] == "ok"
    assert body["project"] == "dtest"
    assert "project_root" in body
    # Daemon's provider is exposed so channels (Telegram /model) can
    # show only the relevant catalogue. Not provided in this fixture → null.
    assert "provider" in body


async def test_health_exposes_serving_pid(aiohttp_client, app) -> None:
    """`_detach_and_report` verifies startup by matching /v1/health's pid
    against the spawned child (live 2026-07-09: a plain TCP probe accepted a
    dying predecessor still holding the port as proof the NEW child serves)."""
    import os

    client = await aiohttp_client(app)
    body = await (await client.get("/v1/health")).json()
    assert body["pid"] == os.getpid()


async def test_health_requires_no_auth(aiohttp_client, app) -> None:
    client = await aiohttp_client(app)
    resp = await client.get("/v1/health")
    assert resp.status == 200


async def test_health_includes_provider_when_set(
    aiohttp_client, project: Project, store: SessionStore, token_store: TokenStore
) -> None:
    """build_state(provider=...) surfaces through /v1/health so channels
    can resolve the daemon's fixed provider."""
    factory = _make_stub_factory(store)
    state = build_state(
        project=project,
        store=store,
        token_store=token_store,
        agent_factory=factory,
        provider="ollama",
    )
    app = make_app(state)
    client = await aiohttp_client(app)
    resp = await client.get("/v1/health")
    body = await resp.json()
    assert body["provider"] == "ollama"


async def test_health_includes_default_model_when_set(
    aiohttp_client, project: Project, store: SessionStore, token_store: TokenStore
) -> None:
    """build_state(default_model=...) is published through /v1/health
    so channels can highlight the active model in their pickers."""
    factory = _make_stub_factory(store)
    state = build_state(
        project=project,
        store=store,
        token_store=token_store,
        agent_factory=factory,
        provider="openrouter",
        default_model="openrouter/anthropic/claude-sonnet-4.6",
    )
    app = make_app(state)
    client = await aiohttp_client(app)
    resp = await client.get("/v1/health")
    body = await resp.json()
    assert body["model"] == "openrouter/anthropic/claude-sonnet-4.6"
    # No override yet → active_model falls back to the daemon default.
    assert body["active_model"] == "openrouter/anthropic/claude-sonnet-4.6"


async def test_health_active_model_is_config_fixed(
    aiohttp_client, project: Project, store: SessionStore, token_store: TokenStore
) -> None:
    """M127: model is fixed at launch — `active_model` always equals the
    configured `default_model`, never a per-session override (a stray
    `SessionOverrides.model` must not leak into the dashboard)."""
    sid = store.create_session()
    factory = _make_stub_factory(store)
    state = build_state(
        project=project,
        store=store,
        token_store=token_store,
        agent_factory=factory,
        provider="openrouter",
        default_model="default-model",
    )
    state.set_overrides(sid, model="picked-model")  # stray; must be ignored
    app = make_app(state)
    client = await aiohttp_client(app)
    body = await (await client.get("/v1/health")).json()
    assert body["model"] == "default-model"
    assert body["active_model"] == "default-model"


# ---- /v1/runs ----


async def test_post_run_requires_auth(aiohttp_client, app) -> None:
    client = await aiohttp_client(app)
    resp = await client.post("/v1/runs", json={"prompt": "hi"})
    assert resp.status == 401


async def test_post_run_rejects_missing_prompt(aiohttp_client, app, good_token: str) -> None:
    client = await aiohttp_client(app)
    resp = await client.post(
        "/v1/runs",
        json={},
        headers={"Authorization": f"Bearer {good_token}"},
    )
    assert resp.status == 400
    body = await resp.json()
    assert "prompt" in body["error"]


async def test_post_run_returns_run_id(aiohttp_client, app, good_token: str) -> None:
    client = await aiohttp_client(app)
    resp = await client.post(
        "/v1/runs",
        json={"prompt": "say hi"},
        headers={"Authorization": f"Bearer {good_token}"},
    )
    assert resp.status == 202
    body = await resp.json()
    assert body["run_id"].startswith("run-")
    assert body["state"] in ("pending", "running", "completed")


async def test_run_completes_and_get_returns_summary(aiohttp_client, app, good_token: str) -> None:
    client = await aiohttp_client(app)
    resp = await client.post(
        "/v1/runs",
        json={"prompt": "hi"},
        headers={"Authorization": f"Bearer {good_token}"},
    )
    body = await resp.json()
    run_id = body["run_id"]

    deadline = time.time() + 5.0
    while time.time() < deadline:
        await asyncio.sleep(0.05)
        resp2 = await client.get(
            f"/v1/runs/{run_id}",
            headers={"Authorization": f"Bearer {good_token}"},
        )
        data = await resp2.json()
        if data["state"] in ("completed", "failed"):
            break
    else:
        pytest.fail("run never reached terminal state")
    assert data["state"] == "completed"
    assert data["stopped_reason"] == "completed"


async def test_get_run_404_unknown_id(aiohttp_client, app, good_token: str) -> None:
    client = await aiohttp_client(app)
    resp = await client.get(
        "/v1/runs/run-doesnotexist",
        headers={"Authorization": f"Bearer {good_token}"},
    )
    assert resp.status == 404


async def test_list_runs_returns_all(aiohttp_client, app, good_token: str) -> None:
    client = await aiohttp_client(app)
    headers = {"Authorization": f"Bearer {good_token}"}
    await client.post("/v1/runs", json={"prompt": "a"}, headers=headers)
    await client.post("/v1/runs", json={"prompt": "b"}, headers=headers)
    resp = await client.get("/v1/runs", headers=headers)
    body = await resp.json()
    assert len(body["runs"]) == 2


# ---- /v1/runs/{run_id}/events (WebSocket) ----


async def _drain_events(ws, *, timeout: float = 3.0) -> list[dict]:
    events: list[dict] = []
    deadline = time.time() + timeout
    while True:
        remaining = max(0.0, deadline - time.time())
        try:
            msg = await asyncio.wait_for(ws.receive(), timeout=remaining)
        except TimeoutError:
            break
        if msg.type == WSMsgType.TEXT:
            events.append(json.loads(msg.data))
            if events[-1].get("type") in ("completed", "error"):
                break
        elif msg.type in (
            WSMsgType.CLOSED,
            WSMsgType.CLOSE,
            WSMsgType.CLOSING,
            WSMsgType.ERROR,
        ):
            break
    return events


async def test_ws_streams_events_to_completion(aiohttp_client, app, good_token: str) -> None:
    client = await aiohttp_client(app)
    headers = {"Authorization": f"Bearer {good_token}"}
    resp = await client.post("/v1/runs", json={"prompt": "hi"}, headers=headers)
    body = await resp.json()
    run_id = body["run_id"]

    async with client.ws_connect(f"/v1/runs/{run_id}/events", headers=headers) as ws:
        events = await _drain_events(ws)
    types = [e["type"] for e in events]
    assert "started" in types
    assert "text_delta" in types
    assert types[-1] == "completed"
    completion = events[-1]
    assert completion["text"] == "hello world"


async def test_ws_replays_buffered_events_after_completion(
    aiohttp_client, app, good_token: str
) -> None:
    """Subscriber connecting after the run finished still receives every event."""
    client = await aiohttp_client(app)
    headers = {"Authorization": f"Bearer {good_token}"}
    resp = await client.post("/v1/runs", json={"prompt": "hi"}, headers=headers)
    body = await resp.json()
    run_id = body["run_id"]

    # Wait until the run finishes.
    deadline = time.time() + 5.0
    while time.time() < deadline:
        await asyncio.sleep(0.05)
        r = await client.get(f"/v1/runs/{run_id}", headers=headers)
        if (await r.json())["state"] in ("completed", "failed"):
            break

    async with client.ws_connect(f"/v1/runs/{run_id}/events", headers=headers) as ws:
        events = await _drain_events(ws)
    assert any(e["type"] == "started" for e in events)
    assert any(e["type"] == "completed" for e in events)


async def test_ws_404_for_unknown_run(aiohttp_client, app, good_token: str) -> None:
    client = await aiohttp_client(app)
    resp = await client.get(
        "/v1/runs/run-nope/events",
        headers={"Authorization": f"Bearer {good_token}"},
    )
    # aiohttp returns 404 on the HTTP upgrade path when the handler bails early.
    assert resp.status == 404


# ---- /v1/sessions ----


async def test_list_sessions_returns_empty_initially(aiohttp_client, app, good_token: str) -> None:
    client = await aiohttp_client(app)
    resp = await client.get("/v1/sessions", headers={"Authorization": f"Bearer {good_token}"})
    assert resp.status == 200
    body = await resp.json()
    assert body["sessions"] == []


async def test_list_sessions_returns_after_run(aiohttp_client, app, good_token: str) -> None:
    client = await aiohttp_client(app)
    headers = {"Authorization": f"Bearer {good_token}"}
    resp = await client.post("/v1/runs", json={"prompt": "hi"}, headers=headers)
    body = await resp.json()
    run_id = body["run_id"]
    deadline = time.time() + 5.0
    while time.time() < deadline:
        await asyncio.sleep(0.05)
        r = await client.get(f"/v1/runs/{run_id}", headers=headers)
        if (await r.json())["state"] in ("completed", "failed"):
            break
    listing = await client.get("/v1/sessions", headers=headers)
    body = await listing.json()
    assert len(body["sessions"]) >= 1
    assert body["sessions"][0]["turn_count"] >= 2  # user + assistant


async def test_get_session_404_unknown(aiohttp_client, app, good_token: str) -> None:
    client = await aiohttp_client(app)
    resp = await client.get(
        "/v1/sessions/unknown-id",
        headers={"Authorization": f"Bearer {good_token}"},
    )
    assert resp.status == 404


async def test_delete_session_404_unknown(aiohttp_client, app, good_token: str) -> None:
    client = await aiohttp_client(app)
    resp = await client.delete(
        "/v1/sessions/unknown-id",
        headers={"Authorization": f"Bearer {good_token}"},
    )
    assert resp.status == 404


async def test_get_then_delete_session(
    aiohttp_client, app, good_token: str, store: SessionStore
) -> None:
    sid = store.create_session()
    store.append_turn(sid, Message(role="user", content="hi"))
    store.append_turn(sid, Message(role="assistant", content="hello"))

    client = await aiohttp_client(app)
    headers = {"Authorization": f"Bearer {good_token}"}
    get = await client.get(f"/v1/sessions/{sid}", headers=headers)
    assert get.status == 200
    body = await get.json()
    assert body["turn_count"] == 2
    assert [m["role"] for m in body["messages"]] == ["user", "assistant"]
    # No PATCH happened on this session → overrides is `null`, not a
    # dict full of `None`s. Callers (TUI status panel, channel ops
    # dashboards) use this to distinguish "session uses daemon
    # defaults" from "session was explicitly overridden but later
    # cleared".
    assert body["overrides"] is None

    delete = await client.delete(f"/v1/sessions/{sid}", headers=headers)
    assert delete.status == 200
    assert (await delete.json())["deleted"] is True

    again = await client.get(f"/v1/sessions/{sid}", headers=headers)
    assert again.status == 404


async def test_get_session_surfaces_mode_override_after_patch(
    aiohttp_client, app, good_token: str, store: SessionStore
) -> None:
    """Observability: once a session has been PATCH'd with a `mode`
    override, GET returns the same dict. (M127: model/provider are fixed
    at launch and rejected by PATCH, so only `mode` is ever set.)"""
    sid = store.create_session()
    store.append_turn(sid, Message(role="user", content="hi"))

    client = await aiohttp_client(app)
    headers = {"Authorization": f"Bearer {good_token}"}
    patch = await client.patch(
        f"/v1/sessions/{sid}",
        json={"mode": "planning"},
        headers=headers,
    )
    assert patch.status == 200

    get = await client.get(f"/v1/sessions/{sid}", headers=headers)
    body = await get.json()
    assert body["overrides"] == {
        "model": None,
        "mode": "planning",
        "provider": None,
    }


async def test_list_sessions_limit_query_clamped(
    aiohttp_client, app, good_token: str, store: SessionStore
) -> None:
    for _ in range(3):
        sid = store.create_session()
        store.append_turn(sid, Message(role="user", content="x"))
    client = await aiohttp_client(app)
    headers = {"Authorization": f"Bearer {good_token}"}
    resp = await client.get("/v1/sessions?limit=2", headers=headers)
    body = await resp.json()
    assert len(body["sessions"]) == 2


async def test_list_sessions_rejects_non_integer_limit(
    aiohttp_client, app, good_token: str
) -> None:
    client = await aiohttp_client(app)
    resp = await client.get(
        "/v1/sessions?limit=banana",
        headers={"Authorization": f"Bearer {good_token}"},
    )
    assert resp.status == 400
