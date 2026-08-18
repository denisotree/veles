"""M234 — `deliver_to` on `POST /v1/runs`.

`POST /v1/runs` could not return its own result: it answers 202 with a summary
that omits the text, and the answer existed only in the WS `completed` event. A
caller that doesn't want to hold a WebSocket now has two ways to get it — read
`final_text` from `GET /v1/runs/{id}`, or hand the daemon a `deliver_to` target
and let the existing DeliveryRouter push it.

Fixtures mirror `tests/test_daemon_server.py`. Note `build_state` deliberately
leaves `delivery_router` unset — production wires it in
`daemon/agent_factory.py::_attach_background_runners` — so the delivery tests
attach a router to the state directly, the idiom from
`tests/test_job_delivery_wiring.py`.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest
from aiohttp import web

from tests.conftest import StubProvider
from veles.channels.delivery import DeliveryRouter
from veles.core.memory import SessionStore
from veles.core.project import Project, init_project
from veles.core.provider import ProviderResponse, StreamEnd, TextDelta, TokenUsage
from veles.core.tools.registry import Registry
from veles.daemon.auth import TokenStore
from veles.daemon.runner import AgentFactory
from veles.daemon.server import build_state, make_app

ANSWER = "hello world"


def _stub_factory(store: SessionStore) -> AgentFactory:
    from veles.core.agent import Agent

    resp = ProviderResponse(
        text=ANSWER,
        tool_calls=[],
        usage=TokenUsage(prompt_tokens=1, completion_tokens=2, total_tokens=3),
        finish_reason="stop",
    )

    def factory(session_id: str | None, *, prompt: str | None = None):
        return Agent(
            provider=StubProvider(
                [resp],
                supports_tools=False,
                supports_streaming=True,
                stream_events=[TextDelta(text=ANSWER), StreamEnd(response=resp)],
                repeat_last=True,
            ),
            registry=Registry(),
            model="stub-model",
            max_iterations=1,
            store=store,
            session_id=session_id or store.create_session(),
        )

    return factory


@pytest.fixture()
def project(tmp_path: Path) -> Project:
    return init_project(tmp_path, name="dtest")


@pytest.fixture()
def store(project: Project):
    # Not closed here, same reasoning as tests/test_daemon_server.py.
    yield SessionStore(project.memory_db_path)


@pytest.fixture()
def token(tmp_path: Path) -> TokenStore:
    ts = TokenStore.load(tmp_path / "daemon.tokens.json")
    ts.add("default")
    return ts


@pytest.fixture()
def state(project: Project, store: SessionStore, token: TokenStore):
    return build_state(
        project=project,
        store=store,
        token_store=token,
        agent_factory=_stub_factory(store),
    )


@pytest.fixture()
def app(state) -> web.Application:
    return make_app(state)


@pytest.fixture()
def auth(token: TokenStore) -> dict[str, str]:
    return {"Authorization": f"Bearer {token.list()[0].token}"}


def _attach_router(state, deliverer) -> None:
    """Wire a real DeliveryRouter with a recording deliverer onto the state.

    A real router (not a duck-typed stand-in) so the test exercises the actual
    `DeliveryTarget` parse + `_deliverers` lookup.
    """
    router = DeliveryRouter()
    router.register_deliverer("telegram", deliverer)
    state.delivery_router = router


async def _wait_for(predicate, *, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.02)
    return False


# ---- delivery happy path ----


async def test_deliver_to_pushes_the_answer_to_the_target(aiohttp_client, state, app, auth):
    """Poll the deliverer's inbox, never `state == "completed"`.

    `state` flips before the hook runs, so keying on it would flake on a race
    that is inherent to the design (documented on `RunHandle.delivery_error`).
    """
    seen: list[tuple[str, str, str | None]] = []

    async def fake(chat_id, text, thread_id):
        seen.append((chat_id, text, thread_id))

    _attach_router(state, fake)
    client = await aiohttp_client(app)

    resp = await client.post(
        "/v1/runs", json={"prompt": "hi", "deliver_to": "telegram:42"}, headers=auth
    )
    assert resp.status == 202

    assert await _wait_for(lambda: bool(seen)), "nothing was delivered"
    assert seen == [("42", ANSWER, None)]


async def test_deliver_to_origin_resolves_against_the_request_origin(
    aiohttp_client, state, app, auth
):
    """`"origin"` is resolved here, not rejected — same vocabulary as task_add."""
    seen: list[tuple[str, str, str | None]] = []

    async def fake(chat_id, text, thread_id):
        seen.append((chat_id, text, thread_id))

    _attach_router(state, fake)
    client = await aiohttp_client(app)

    resp = await client.post(
        "/v1/runs",
        json={"prompt": "hi", "deliver_to": "origin", "origin": "telegram:77"},
        headers=auth,
    )
    assert resp.status == 202
    assert await _wait_for(lambda: bool(seen))
    assert seen[0][0] == "77"


async def test_delivery_failure_does_not_fail_the_run(aiohttp_client, state, app, auth):
    """A chat that can't be reached says nothing about whether the agent worked."""

    async def boom(chat_id, text, thread_id):
        raise RuntimeError("telegram sendMessage failed: 403")

    _attach_router(state, boom)
    client = await aiohttp_client(app)

    resp = await client.post(
        "/v1/runs", json={"prompt": "hi", "deliver_to": "telegram:42"}, headers=auth
    )
    run_id = (await resp.json())["run_id"]

    async def _terminal() -> dict:
        assert await _wait_for(
            lambda: (
                state.get_run(run_id) is not None
                and state.get_run(run_id).state in ("completed", "failed")
            )
        )
        got = await client.get(f"/v1/runs/{run_id}", headers=auth)
        return await got.json()

    body = await _terminal()
    assert body["state"] == "completed"
    assert body["error"] is None
    assert await _wait_for(lambda: state.get_run(run_id).delivery_error is not None)
    assert "403" in state.get_run(run_id).delivery_error


# ---- request validation ----


@pytest.mark.parametrize("bad", ["telegram", "nonsense", "", "   ", 42])
async def test_malformed_deliver_to_is_rejected(aiohttp_client, app, auth, bad):
    client = await aiohttp_client(app)
    resp = await client.post("/v1/runs", json={"prompt": "hi", "deliver_to": bad}, headers=auth)
    assert resp.status == 400
    assert "deliver_to" in (await resp.json())["error"]


async def test_deliver_to_origin_without_an_origin_is_rejected(aiohttp_client, app, auth):
    client = await aiohttp_client(app)
    resp = await client.post(
        "/v1/runs", json={"prompt": "hi", "deliver_to": "origin"}, headers=auth
    )
    assert resp.status == 400
    assert "origin" in (await resp.json())["error"]


async def test_malformed_origin_is_rejected(aiohttp_client, app, auth):
    """`origin` is consumed AS a delivery target by task_add/job_add, so it has
    to satisfy the same grammar — otherwise a bad value only blows up later,
    inside an agent tool call."""
    client = await aiohttp_client(app)
    resp = await client.post("/v1/runs", json={"prompt": "hi", "origin": "nonsense"}, headers=auth)
    assert resp.status == 400
    assert "origin" in (await resp.json())["error"]


async def test_deliver_to_without_a_router_is_503(aiohttp_client, app, auth):
    """`build_state` leaves the router unset, so this is the default state —
    fail loudly rather than accept a delivery contract we cannot honour."""
    client = await aiohttp_client(app)
    resp = await client.post(
        "/v1/runs", json={"prompt": "hi", "deliver_to": "telegram:42"}, headers=auth
    )
    assert resp.status == 503


async def test_run_without_deliver_to_is_unaffected(aiohttp_client, app, auth):
    client = await aiohttp_client(app)
    resp = await client.post("/v1/runs", json={"prompt": "hi"}, headers=auth)
    assert resp.status == 202


# ---- final_text is readable without a WebSocket ----


async def test_get_run_carries_final_text(aiohttp_client, state, app, auth):
    client = await aiohttp_client(app)
    run_id = (await (await client.post("/v1/runs", json={"prompt": "hi"}, headers=auth)).json())[
        "run_id"
    ]
    assert await _wait_for(
        lambda: state.get_run(run_id) is not None and state.get_run(run_id).done.is_set()
    )

    body = await (await client.get(f"/v1/runs/{run_id}", headers=auth)).json()
    assert body["final_text"] == ANSWER
    assert body["delivery_error"] is None


async def test_list_runs_does_not_carry_final_text(aiohttp_client, state, app, auth):
    """Locks the deliberate asymmetry with GET.

    `state.runs` is never pruned, so putting the text in `to_summary` would grow
    the list response by every answer for the daemon's whole lifetime.
    """
    client = await aiohttp_client(app)
    await client.post("/v1/runs", json={"prompt": "hi"}, headers=auth)

    body = await (await client.get("/v1/runs", headers=auth)).json()
    assert body["runs"], "expected at least one run"
    for entry in body["runs"]:
        assert "final_text" not in entry


# ---- the manager path delivers too ----


async def test_manager_path_delivers(monkeypatch, store):
    """Driven directly rather than through HTTP: the manager branch needs a
    `worker_agent_factory` plus a keyword-matching prompt, and `decompose_and_run`
    has to be patched anyway — going via the endpoint would test the routing
    heuristic, not the delivery hook."""
    from veles.core.orchestration.manager import ManagerRunResult
    from veles.core.orchestration.workers import WorkerPlan
    from veles.daemon.runner import new_run_handle, run_manager_in_background

    def fake_decompose(prompt, *, agent_factory, **kwargs):
        return ManagerRunResult(
            final_text="manager answer",
            handles=(),
            plan=WorkerPlan(objective=prompt),
            error=None,
        )

    monkeypatch.setattr("veles.core.orchestration.decompose_and_run", fake_decompose)

    seen: list[str] = []

    async def deliver(text: str) -> None:
        seen.append(text)

    handle = new_run_handle(session_id=None)
    await run_manager_in_background(
        handle,
        worker_agent_factory=lambda **kw: None,
        prompt="research everything thoroughly",
        deliver_hook=deliver,
    )

    assert handle.final_text == "manager answer"
    assert seen == ["manager answer"]
