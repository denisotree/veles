"""M280 a1: `POST /v1/runs` and the in-process channel backend start a turn
through one function, `daemon/turns.py::start_turn`.

Agent modes (M280) are routed there, so a front door that bypassed it would
silently ignore the chat's mode — the very defect M280 fixes. These tests pin
that both doors go through it, and the one behaviour the merge changed.
"""

from __future__ import annotations

import pytest
from aiohttp import web

from veles.channels.in_process_backend import InProcessRunBackend
from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.daemon.auth import TokenStore
from veles.daemon.server import build_state, make_app


@pytest.fixture()
def state(tmp_path):
    project = init_project(tmp_path / "proj", name="proj")
    store = SessionStore(project.memory_db_path)
    tokens = TokenStore.load(tmp_path / "tokens.json")
    tokens.add("default")
    st = build_state(
        project=project,
        store=store,
        token_store=tokens,
        agent_factory=lambda session_id, *, prompt=None: _Agent(),
    )
    yield st
    store.close()


class _Agent:
    session_id = "ses-1"

    def run(self, prompt, *, on_text_delta, event_listener=None):  # pragma: no cover
        raise AssertionError("the run itself is replaced in these tests")


@pytest.fixture()
def recorded(monkeypatch):
    """Replace the background run with a recorder, so what is under test is
    which door reached `start_turn`, not the agent loop."""
    calls: list[str] = []

    async def fake_run(handle, *, agent, prompt, **_kw):
        calls.append(prompt)
        handle.done.set()  # else the app's shutdown drain waits out its timeout

    monkeypatch.setattr("veles.daemon.turns.run_agent_in_background", fake_run)
    return calls


async def test_the_channel_backend_starts_turns_through_start_turn(state, recorded) -> None:
    await InProcessRunBackend(state).submit_run("from telegram")
    for task in list(state.run_tasks):
        await task
    assert recorded == ["from telegram"]


async def test_post_v1_runs_starts_turns_through_start_turn(
    aiohttp_client, state, recorded
) -> None:
    app: web.Application = make_app(state)
    client = await aiohttp_client(app)
    token = state.token_store.list()[0].token
    resp = await client.post(
        "/v1/runs", json={"prompt": "from http"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status == 202
    for task in list(state.run_tasks):
        await task
    assert recorded == ["from http"]


async def test_a_failed_agent_build_marks_the_channel_run_failed(state) -> None:
    """The HTTP door always did this; the channel door left the run "pending"
    forever. The exception still reaches the caller, as before."""

    def broken_factory(session_id, *, prompt=None):
        raise RuntimeError("no API key")

    state.agent_factory = broken_factory
    with pytest.raises(RuntimeError, match="no API key"):
        await InProcessRunBackend(state).submit_run("hi")
    (run,) = state.list_runs()
    assert run.state == "failed"
    assert "no API key" in (run.error or "")
