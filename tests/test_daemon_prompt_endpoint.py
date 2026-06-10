"""`POST /v1/runs/{run_id}/prompts/{prompt_id}` — the daemon's other half
of the channel-prompt protocol. Sets the `concurrent.futures.Future`
held in the matching `PendingPrompt` so the blocked worker thread
unblocks and the agent gets its answer."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from aiohttp import web

from veles.core.job_runner import JobRunner
from veles.core.jobs_store import JobsStore
from veles.core.memory import SessionStore
from veles.core.project import Project, init_project
from veles.daemon.auth import TokenStore
from veles.daemon.runner import PendingPrompt, RunHandle
from veles.daemon.server import build_state, make_app


@pytest.fixture()
def project(tmp_path: Path) -> Project:
    return init_project(tmp_path, name="ptest")


@pytest.fixture()
def store(project: Project) -> Iterator[SessionStore]:
    s = SessionStore(project.memory_db_path)
    yield s
    s.close()


@pytest.fixture()
def jobs_store(project: Project) -> Iterator[JobsStore]:
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
    def _factory(session_id, *, prompt=None):  # noqa: ARG001
        raise AssertionError("not invoked by this test")

    state = build_state(
        project=project,
        store=store,
        token_store=token_store,
        agent_factory=_factory,
    )
    state.job_runner = JobRunner(
        store=jobs_store, agent_factory=_factory, output_root=tmp_path / "jobs"
    )
    return make_app(state)


def _install_pending(state, *, run_id: str, prompt_id: str, kind: str = "trust") -> PendingPrompt:
    handle = RunHandle(run_id=run_id, session_id=None)
    pending = PendingPrompt(
        kind=kind,
        tool="Bash",
        valid_choices=("once", "always_project", "refuse")
        if kind == "trust"
        else ("yes", "no"),
    )
    handle.pending_prompts[prompt_id] = pending
    state.add_run(handle)
    # The aiohttp test client tears the app down on each test, and
    # `_drain_in_flight_runs` waits up to 10s per unfinished run. We're
    # not running real agents here — mark done so teardown is instant.
    handle.done.set()
    return pending


async def test_resolve_prompt_unblocks_future_and_emits_event(
    aiohttp_client, app, good_token: str
) -> None:
    state = app["state"]
    pending = _install_pending(state, run_id="run-A", prompt_id="abcd1234")
    client = await aiohttp_client(app)
    resp = await client.post(
        "/v1/runs/run-A/prompts/abcd1234",
        json={"choice": "once"},
        headers={"Authorization": f"Bearer {good_token}"},
    )
    assert resp.status == 200
    body = await resp.json()
    assert body == {"accepted": True, "choice": "once"}
    assert pending.future.done()
    assert pending.future.result() == "once"
    # The endpoint should have emitted prompt_resolved so other
    # subscribers (or a watching channel) see the close-out.
    handle = state.get_run("run-A")
    types = [e["type"] for e in handle.events]
    assert "prompt_resolved" in types
    resolved = next(e for e in handle.events if e["type"] == "prompt_resolved")
    assert resolved["prompt_id"] == "abcd1234"
    assert resolved["choice"] == "once"


async def test_resolve_prompt_404_when_run_unknown(
    aiohttp_client, app, good_token: str
) -> None:
    client = await aiohttp_client(app)
    resp = await client.post(
        "/v1/runs/run-missing/prompts/xx",
        json={"choice": "once"},
        headers={"Authorization": f"Bearer {good_token}"},
    )
    assert resp.status == 404


async def test_resolve_prompt_404_when_prompt_unknown(
    aiohttp_client, app, good_token: str
) -> None:
    state = app["state"]
    _install_pending(state, run_id="run-B", prompt_id="aaaa1111")
    client = await aiohttp_client(app)
    resp = await client.post(
        "/v1/runs/run-B/prompts/zzzz",  # wrong prompt id
        json={"choice": "once"},
        headers={"Authorization": f"Bearer {good_token}"},
    )
    assert resp.status == 404


async def test_resolve_prompt_409_on_invalid_choice_and_remains_pending(
    aiohttp_client, app, good_token: str
) -> None:
    state = app["state"]
    pending = _install_pending(state, run_id="run-C", prompt_id="cccc")
    client = await aiohttp_client(app)
    resp = await client.post(
        "/v1/runs/run-C/prompts/cccc",
        json={"choice": "maybe"},
        headers={"Authorization": f"Bearer {good_token}"},
    )
    assert resp.status == 409
    body = await resp.json()
    assert "valid_choices" in body
    # Pending must still be there so a corrected POST can resolve it.
    handle = state.get_run("run-C")
    assert "cccc" in handle.pending_prompts
    assert not pending.future.done()


async def test_resolve_prompt_400_on_malformed_body(
    aiohttp_client, app, good_token: str
) -> None:
    state = app["state"]
    _install_pending(state, run_id="run-D", prompt_id="dddd")
    client = await aiohttp_client(app)
    resp = await client.post(
        "/v1/runs/run-D/prompts/dddd",
        json={"oops": "no choice field"},
        headers={"Authorization": f"Bearer {good_token}"},
    )
    assert resp.status == 400


async def test_resolve_prompt_401_without_token(
    aiohttp_client, app
) -> None:
    state = app["state"]
    _install_pending(state, run_id="run-E", prompt_id="eeee")
    client = await aiohttp_client(app)
    resp = await client.post(
        "/v1/runs/run-E/prompts/eeee",
        json={"choice": "once"},
    )
    assert resp.status == 401


async def test_double_resolve_returns_404(
    aiohttp_client, app, good_token: str
) -> None:
    state = app["state"]
    _install_pending(state, run_id="run-F", prompt_id="ffff")
    client = await aiohttp_client(app)
    resp1 = await client.post(
        "/v1/runs/run-F/prompts/ffff",
        json={"choice": "refuse"},
        headers={"Authorization": f"Bearer {good_token}"},
    )
    assert resp1.status == 200
    resp2 = await client.post(
        "/v1/runs/run-F/prompts/ffff",
        json={"choice": "once"},
        headers={"Authorization": f"Bearer {good_token}"},
    )
    assert resp2.status == 404
