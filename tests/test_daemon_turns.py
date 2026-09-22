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


# ---- a5: the session's mode picks the path ----


class _ModeAgent:
    def __init__(self, session_id, mode):
        self.session_id = session_id
        self.mode = mode

    def run(self, prompt, *, on_text_delta=None, event_listener=None):
        from veles.core.agent import RunResult

        text = f"{self.mode or 'default'} answer"
        if on_text_delta is not None:
            on_text_delta(text)
        return RunResult(text=text, iterations=1, session_id=self.session_id)


@pytest.fixture()
def built(state) -> list[tuple[str | None, str | None]]:
    """(session_id, mode) of every agent the daemon's factory builds."""
    calls: list[tuple[str | None, str | None]] = []

    def factory(session_id, *, prompt=None, mode=None, extra_system=None, toolless=False):
        sid = session_id or state.store.create_session()
        calls.append((sid, mode))
        return _ModeAgent(sid, mode)

    state.agent_factory = factory
    return calls


async def _finish(state, payload) -> str | None:
    for task in list(state.run_tasks):
        await task
    return state.get_run(payload["run_id"]).final_text


async def test_a_chat_switched_to_planning_gets_a_planning_turn(state, built) -> None:
    """The M280 defect: `/mode planning` was stored and the turn ran the plain
    writing agent anyway."""
    sid = state.store.create_session()
    state.set_chat_mode(sid, "planning")
    payload = await InProcessRunBackend(state).submit_run("design X", session_id=sid)
    assert await _finish(state, payload) == "planning answer"
    assert built == [(sid, "planning")]


async def test_a_chat_on_its_default_runs_exactly_as_before(state, built) -> None:
    sid = state.store.create_session()
    payload = await InProcessRunBackend(state).submit_run("hi", session_id=sid)
    assert await _finish(state, payload) == "default answer"
    assert built == [(sid, None)]


async def test_a_chosen_mode_wins_over_the_manager_gate(state, built, monkeypatch) -> None:
    monkeypatch.setenv("VELES_MANAGER_MODE", "1")
    state.worker_agent_factory = lambda **kw: None

    def boom(*a, **kw):
        raise AssertionError("the manager must not run for a chat with a chosen mode")

    monkeypatch.setattr("veles.core.orchestration.decompose_and_run", boom)
    sid = state.store.create_session()
    state.set_chat_mode(sid, "writing")
    payload = await InProcessRunBackend(state).submit_run("research everything", session_id=sid)
    assert await _finish(state, payload) == "writing answer"


async def test_a_stale_session_keeps_its_chosen_mode(state, built) -> None:
    """A channel map can outlive its session row; the turn continues in a fresh
    session, and the chat's mode must come along rather than silently reset."""
    state.set_chat_mode("gone-sess", "planning")
    payload = await InProcessRunBackend(state).submit_run("hi", session_id="gone-sess")
    await _finish(state, payload)
    (fresh, mode) = built[0]
    assert fresh != "gone-sess" and mode == "planning"
    assert payload["session_id"] == fresh  # the gateway maps the chat to it
    assert state.chat_mode(fresh).mode == "planning"
    assert "gone-sess" not in state.chat_modes


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
