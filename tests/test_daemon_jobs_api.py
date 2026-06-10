"""M75 — daemon /v1/jobs CRUD + trigger + runs endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
from aiohttp import web

from tests.conftest import StubProvider
from veles.core.job_runner import JobRunner
from veles.core.jobs_store import JobsStore
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


def _make_stub_factory(store: SessionStore):
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
def jobs_store(project: Project):
    s = JobsStore(project.memory_db_path)
    yield s
    s.close()


@pytest.fixture()
def token_store(tmp_path: Path) -> TokenStore:
    ts = TokenStore.load(tmp_path / "daemon.tokens.json")
    ts.add("default")
    return ts


@pytest.fixture()
def good_token(token_store: TokenStore) -> str:
    return token_store.list()[0].token


@pytest.fixture()
def app(
    project: Project,
    store: SessionStore,
    jobs_store: JobsStore,
    token_store: TokenStore,
    tmp_path: Path,
) -> web.Application:
    factory = _make_stub_factory(store)
    state = build_state(
        project=project,
        store=store,
        token_store=token_store,
        agent_factory=factory,
    )
    state.job_runner = JobRunner(
        store=jobs_store,
        agent_factory=factory,
        output_root=tmp_path / "jobs-out",
    )
    return make_app(state)


async def test_post_jobs_creates(aiohttp_client, app, good_token: str) -> None:
    client = await aiohttp_client(app)
    resp = await client.post(
        "/v1/jobs",
        json={"name": "t", "prompt": "say hi", "schedule": "30m"},
        headers={"Authorization": f"Bearer {good_token}"},
    )
    assert resp.status == 201
    body = await resp.json()
    assert body["id"].startswith("job-")
    assert body["schedule"]["kind"] == "interval"
    assert body["enabled"] is True


async def test_post_jobs_rejects_bad_schedule(aiohttp_client, app, good_token: str) -> None:
    client = await aiohttp_client(app)
    resp = await client.post(
        "/v1/jobs",
        json={"name": "t", "prompt": "x", "schedule": "garbage"},
        headers={"Authorization": f"Bearer {good_token}"},
    )
    assert resp.status == 400


async def test_get_jobs_lists(aiohttp_client, app, good_token: str) -> None:
    client = await aiohttp_client(app)
    await client.post(
        "/v1/jobs",
        json={"name": "t", "prompt": "x", "schedule": "1h"},
        headers={"Authorization": f"Bearer {good_token}"},
    )
    resp = await client.get(
        "/v1/jobs", headers={"Authorization": f"Bearer {good_token}"}
    )
    assert resp.status == 200
    body = await resp.json()
    assert len(body["jobs"]) == 1
    assert body["jobs"][0]["name"] == "t"


async def test_patch_job_updates(aiohttp_client, app, good_token: str) -> None:
    client = await aiohttp_client(app)
    create = await client.post(
        "/v1/jobs",
        json={"name": "t", "prompt": "x", "schedule": "1h"},
        headers={"Authorization": f"Bearer {good_token}"},
    )
    jid = (await create.json())["id"]
    resp = await client.patch(
        f"/v1/jobs/{jid}",
        json={"enabled": False},
        headers={"Authorization": f"Bearer {good_token}"},
    )
    assert resp.status == 200
    body = await resp.json()
    assert body["enabled"] is False


async def test_post_trigger(aiohttp_client, app, good_token: str) -> None:
    client = await aiohttp_client(app)
    create = await client.post(
        "/v1/jobs",
        json={"name": "t", "prompt": "x", "schedule": "1h"},
        headers={"Authorization": f"Bearer {good_token}"},
    )
    jid = (await create.json())["id"]
    resp = await client.post(
        f"/v1/jobs/{jid}/trigger",
        headers={"Authorization": f"Bearer {good_token}"},
    )
    assert resp.status == 200


async def test_get_runs_empty(aiohttp_client, app, good_token: str) -> None:
    client = await aiohttp_client(app)
    create = await client.post(
        "/v1/jobs",
        json={"name": "t", "prompt": "x", "schedule": "1h"},
        headers={"Authorization": f"Bearer {good_token}"},
    )
    jid = (await create.json())["id"]
    resp = await client.get(
        f"/v1/jobs/{jid}/runs",
        headers={"Authorization": f"Bearer {good_token}"},
    )
    assert resp.status == 200
    body = await resp.json()
    assert body["runs"] == []


async def test_delete_job(aiohttp_client, app, good_token: str) -> None:
    client = await aiohttp_client(app)
    create = await client.post(
        "/v1/jobs",
        json={"name": "t", "prompt": "x", "schedule": "1h"},
        headers={"Authorization": f"Bearer {good_token}"},
    )
    jid = (await create.json())["id"]
    resp = await client.delete(
        f"/v1/jobs/{jid}",
        headers={"Authorization": f"Bearer {good_token}"},
    )
    assert resp.status == 200
    # subsequent get → 404
    resp2 = await client.get(
        f"/v1/jobs/{jid}",
        headers={"Authorization": f"Bearer {good_token}"},
    )
    assert resp2.status == 404


async def test_post_requires_auth(aiohttp_client, app) -> None:
    client = await aiohttp_client(app)
    resp = await client.post("/v1/jobs", json={"name": "x", "prompt": "x", "schedule": "1h"})
    assert resp.status == 401


async def test_when_scheduler_not_enabled_returns_503(
    aiohttp_client,
    project: Project,
    store: SessionStore,
    token_store: TokenStore,
    good_token: str,
) -> None:
    factory = _make_stub_factory(store)
    state = build_state(
        project=project,
        store=store,
        token_store=token_store,
        agent_factory=factory,
    )
    # NB: no state.job_runner assigned
    app = make_app(state)
    client = await aiohttp_client(app)
    resp = await client.post(
        "/v1/jobs",
        json={"name": "t", "prompt": "x", "schedule": "1h"},
        headers={"Authorization": f"Bearer {good_token}"},
    )
    assert resp.status == 503
