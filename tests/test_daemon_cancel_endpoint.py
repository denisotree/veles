"""`POST /v1/runs/{run_id}/cancel` (M225) — stop an in-flight turn.

Cooperative: the endpoint only flips the handle's `CancelToken`. The
agent thread notices at its next checkpoint and finishes with
`stopped_reason="cancelled"`, so the event stream still terminates
normally for anyone subscribed.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from aiohttp import web

from veles.core.memory import SessionStore
from veles.core.project import Project, init_project
from veles.daemon.auth import TokenStore
from veles.daemon.runner import RunHandle
from veles.daemon.server import build_state, make_app


@pytest.fixture()
def project(tmp_path: Path) -> Project:
    return init_project(tmp_path, name="ctest")


@pytest.fixture()
def store(project: Project) -> Iterator[SessionStore]:
    s = SessionStore(project.memory_db_path)
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
def app(project: Project, store: SessionStore, token_store: TokenStore) -> web.Application:
    def _factory(session_id, *, prompt=None):
        raise AssertionError("not invoked by this test")

    return make_app(
        build_state(
            project=project,
            store=store,
            token_store=token_store,
            agent_factory=_factory,
        )
    )


def _install_run(state, *, run_id: str, state_name: str = "running") -> RunHandle:
    handle = RunHandle(run_id=run_id, session_id=None, state=state_name)
    state.add_run(handle)
    if state_name != "running":
        handle.done.set()
    return handle


async def test_cancel_sets_the_token(aiohttp_client, app, good_token: str) -> None:
    handle = _install_run(app["state"], run_id="run-A")
    client = await aiohttp_client(app)
    resp = await client.post(
        "/v1/runs/run-A/cancel", json={}, headers={"Authorization": f"Bearer {good_token}"}
    )
    assert resp.status == 200
    assert (await resp.json())["cancelled"] is True
    assert handle.cancel_token.cancelled
    handle.done.set()  # keep teardown's in-flight drain instant


async def test_cancel_is_a_noop_on_a_finished_run(aiohttp_client, app, good_token: str) -> None:
    handle = _install_run(app["state"], run_id="run-B", state_name="completed")
    client = await aiohttp_client(app)
    resp = await client.post(
        "/v1/runs/run-B/cancel", json={}, headers={"Authorization": f"Bearer {good_token}"}
    )
    assert resp.status == 200
    assert (await resp.json())["cancelled"] is False
    assert not handle.cancel_token.cancelled


async def test_cancel_404_when_run_unknown(aiohttp_client, app, good_token: str) -> None:
    client = await aiohttp_client(app)
    resp = await client.post(
        "/v1/runs/nope/cancel", json={}, headers={"Authorization": f"Bearer {good_token}"}
    )
    assert resp.status == 404


async def test_token_reaches_the_worker_thread_and_stream_terminates() -> None:
    """The whole point of the token: the agent runs on a worker thread
    that can't be killed, so it has to *see* the flag. Cancel while it
    spins, and the run still ends with a clean `completed` event."""
    import asyncio

    from veles.core.agent import RunResult
    from veles.core.cancel import current_cancel_token
    from veles.daemon.runner import new_run_handle, run_agent_in_background

    started = asyncio.Event()
    loop = asyncio.get_running_loop()

    class _SpinningAgent:
        def run(self, prompt, on_text_delta=None, event_listener=None):
            token = current_cancel_token()
            assert token is not None, "cancel token did not reach the worker thread"
            loop.call_soon_threadsafe(started.set)
            while not token.cancelled:
                pass
            # What Agent.run does on TurnCancelled.
            return RunResult(text="", iterations=0, stopped_reason="cancelled", session_id="s1")

    handle = new_run_handle(session_id="s1")
    task = asyncio.create_task(run_agent_in_background(handle, agent=_SpinningAgent(), prompt="q"))
    await started.wait()
    assert handle.request_cancel() is True
    await task
    completed = [e for e in handle.events if e["type"] == "completed"]
    assert completed and completed[0]["stopped_reason"] == "cancelled"
    assert handle.request_cancel() is False  # nothing left to cancel
