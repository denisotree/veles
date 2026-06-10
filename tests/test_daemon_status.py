"""M74 — /v1/status (extended health) and /v1/channels endpoints."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from aiohttp import web

from tests.conftest import StubProvider
from veles.channels.session_map import SessionMap, channel_session_path
from veles.core.memory import SessionStore
from veles.core.project import Project, init_project
from veles.core.provider import (
    ProviderResponse,
    StreamEnd,
    TextDelta,
    TokenUsage,
)
from veles.core.tools.registry import Registry
from veles.daemon.auth import TokenStore
from veles.daemon.runner import AgentFactory
from veles.daemon.server import build_state, make_app


def _StubProvider() -> StubProvider:
    resp = ProviderResponse(
        text="ok",
        tool_calls=[],
        usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        finish_reason="stop",
    )
    return StubProvider(
        [resp],
        supports_tools=False,
        supports_streaming=True,
        stream_events=[TextDelta(text="ok"), StreamEnd(response=resp)],
        repeat_last=True,
    )


def _make_stub_factory(store: SessionStore) -> AgentFactory:
    from veles.core.agent import Agent

    def factory(session_id: str | None):
        sid = session_id or store.create_session()
        return Agent(
            provider=_StubProvider(),
            registry=Registry(),
            model="stub-model",
            max_iterations=1,
            store=store,
            session_id=sid,
        )

    return factory


@pytest.fixture()
def project(tmp_path: Path) -> Project:
    return init_project(tmp_path, name="dtest")


@pytest.fixture()
def store(project: Project):
    s = SessionStore(project.memory_db_path)
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
    state = build_state(
        project=project,
        store=store,
        token_store=token_store,
        agent_factory=_make_stub_factory(store),
    )
    return make_app(state)


# ---- /v1/status ----


async def test_status_requires_auth(aiohttp_client, app) -> None:
    client = await aiohttp_client(app)
    resp = await client.get("/v1/status")
    assert resp.status == 401


async def test_status_reports_no_jobs_or_dream_when_unwired(
    aiohttp_client, app, good_token: str
) -> None:
    client = await aiohttp_client(app)
    resp = await client.get("/v1/status", headers={"Authorization": f"Bearer {good_token}"})
    assert resp.status == 200
    body = await resp.json()
    assert body["status"] == "ok"
    assert body["project"] == "dtest"
    assert body["runs"] == {"total": 0, "active": 0}
    assert body["jobs"] is None
    assert body["dream"] is None
    assert "last_activity_at" in body


async def test_status_reflects_runs_after_post(
    aiohttp_client, app, good_token: str
) -> None:
    client = await aiohttp_client(app)
    await client.post(
        "/v1/runs",
        json={"prompt": "ping"},
        headers={"Authorization": f"Bearer {good_token}"},
    )
    # Give the worker a moment to start (but don't require completion).
    await asyncio.sleep(0.05)
    resp = await client.get("/v1/status", headers={"Authorization": f"Bearer {good_token}"})
    body = await resp.json()
    assert body["runs"]["total"] >= 1


async def test_status_picks_up_runner_status_method(
    aiohttp_client, app, good_token: str
) -> None:
    class _Stub:
        def status(self) -> dict[str, object]:
            return {"enabled": True, "due": 3}

    app["state"].job_runner = _Stub()
    app["state"].dream_runner = _Stub()
    client = await aiohttp_client(app)
    resp = await client.get("/v1/status", headers={"Authorization": f"Bearer {good_token}"})
    body = await resp.json()
    assert body["jobs"] == {"enabled": True, "due": 3}
    assert body["dream"] == {"enabled": True, "due": 3}


async def test_status_reports_active_channels(
    aiohttp_client, app, good_token: str
) -> None:
    """The status docstring has always promised `channels`; it now surfaces
    the actually-running set (`state.active_channels`)."""
    client = await aiohttp_client(app)
    empty = await (
        await client.get("/v1/status", headers={"Authorization": f"Bearer {good_token}"})
    ).json()
    assert empty["channels"] == []
    app["state"].active_channels.append("telegram")
    body = await (
        await client.get("/v1/status", headers={"Authorization": f"Bearer {good_token}"})
    ).json()
    assert body["channels"] == ["telegram"]


async def test_health_reports_active_channels(aiohttp_client, app) -> None:
    """`/v1/health` (unauth, the TUI picker's source) surfaces the live
    channel set so the picker reflects what the daemon actually serves."""
    client = await aiohttp_client(app)
    empty = await (await client.get("/v1/health")).json()
    assert empty["channels"] == []
    app["state"].active_channels.append("telegram")
    body = await (await client.get("/v1/health")).json()
    assert body["channels"] == ["telegram"]


# ---- /v1/channels ----


async def test_channels_lists_registered_platforms(
    aiohttp_client, app, good_token: str, isolated_user_home: Path
) -> None:
    client = await aiohttp_client(app)
    resp = await client.get("/v1/channels", headers={"Authorization": f"Bearer {good_token}"})
    assert resp.status == 200
    body = await resp.json()
    platforms = [c["platform"] for c in body["channels"]]
    assert "telegram" in platforms


async def test_channels_counts_persisted_sessions(
    aiohttp_client, app, good_token: str, isolated_user_home: Path
) -> None:
    sm = SessionMap.load(channel_session_path("telegram"))
    sm.set("42", "ses-abc")
    sm.set("99", "ses-xyz")
    client = await aiohttp_client(app)
    resp = await client.get("/v1/channels", headers={"Authorization": f"Bearer {good_token}"})
    body = await resp.json()
    tg = next(c for c in body["channels"] if c["platform"] == "telegram")
    assert tg["sessions"] == 2
