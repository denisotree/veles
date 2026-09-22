"""InProcessRunBackend exposes the channel-facing `RunBackend` Protocol
backed by the daemon's own AgentFactory / RunHandle plumbing.

Tests stub the agent to drive deterministic events.
"""

from __future__ import annotations

import asyncio

import pytest

from veles.channels.in_process_backend import InProcessRunBackend
from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.daemon.auth import TokenStore
from veles.daemon.state import DaemonState


class _StubAgent:
    def __init__(self, *, deltas: list[str], final_text: str, session_id: str = "ses-test") -> None:
        self._deltas = deltas
        self._final = final_text
        self._sid = session_id

    def run(self, prompt: str, *, on_text_delta, event_listener=None):
        for d in self._deltas:
            on_text_delta(d)
        from veles.core.agent import RunResult

        return RunResult(
            text=self._final,
            iterations=1,
            stopped_reason="completed",
            session_id=self._sid,
        )


def _build_state(tmp_path):
    project = init_project(tmp_path, name=None, force=False)
    store = SessionStore(project.memory_db_path)
    tokens = TokenStore.load()

    def factory(session_id, *, prompt=None):
        return _StubAgent(deltas=["he", "llo"], final_text="hello")

    return DaemonState(
        project=project,
        store=store,
        token_store=tokens,
        agent_factory=factory,
        started_at=0.0,
    )


async def test_submit_run_returns_run_id_and_session(tmp_path) -> None:
    state = _build_state(tmp_path)
    backend = InProcessRunBackend(state)
    payload = await backend.submit_run("hi", session_id="ses-1")
    assert "run_id" in payload
    assert payload["session_id"] == "ses-1"


async def test_channel_routes_through_manager_when_opted_in(tmp_path, monkeypatch) -> None:
    """M122f: with VELES_MANAGER_MODE=1 and a worker factory wired, a channel
    turn dispatches via the manager (decompose_and_run), not the direct agent."""
    monkeypatch.setenv("VELES_MANAGER_MODE", "1")
    state = _build_state(tmp_path)

    used_worker_factory = {"called": False}

    def worker_factory(**kwargs):
        used_worker_factory["called"] = True
        raise AssertionError("not reached — decompose_and_run is stubbed")

    state.worker_agent_factory = worker_factory

    captured = {}

    def fake_decompose(prompt, *, agent_factory, **kw):
        captured["prompt"] = prompt
        from veles.core.orchestration.manager import ManagerRunResult
        from veles.core.orchestration.workers import WorkerPlan

        return ManagerRunResult(
            final_text="manager answer", handles=(), plan=WorkerPlan(objective="o")
        )

    monkeypatch.setattr("veles.core.orchestration.decompose_and_run", fake_decompose)

    backend = InProcessRunBackend(state)
    payload = await backend.submit_run("do the thing")
    for task in list(state.run_tasks):
        await asyncio.wait_for(task, timeout=2.0)
    assert captured["prompt"] == "do the thing"
    handle = state.get_run(payload["run_id"])
    assert handle is not None
    assert any(e.get("type") == "completed" for e in handle.events)


async def test_channel_stays_direct_when_not_opted_in(tmp_path, monkeypatch) -> None:
    """Default (no env) → channel turn uses the single-agent path even with a
    worker factory present."""
    monkeypatch.delenv("VELES_MANAGER_MODE", raising=False)
    state = _build_state(tmp_path)
    state.worker_agent_factory = lambda **kw: None  # present but must be unused

    def boom(*a, **kw):
        raise AssertionError("decompose_and_run must not run when opt-in is off")

    monkeypatch.setattr("veles.core.orchestration.decompose_and_run", boom)

    backend = InProcessRunBackend(state)
    await backend.submit_run("hi")
    for task in list(state.run_tasks):
        await asyncio.wait_for(task, timeout=2.0)


async def test_stream_events_yields_started_text_completed(tmp_path) -> None:
    state = _build_state(tmp_path)
    backend = InProcessRunBackend(state)
    payload = await backend.submit_run("hi")
    run_id = payload["run_id"]

    events: list[dict] = []
    async for event in backend.stream_events(run_id):
        events.append(event)
        if event.get("type") == "completed":
            break
    kinds = [e.get("type") for e in events]
    assert kinds[0] == "started"
    assert "text_delta" in kinds
    assert kinds[-1] == "completed"
    final = events[-1]
    assert final.get("text") == "hello"
    # drain any pending agent task before tmp_path is removed
    for task in list(state.run_tasks):
        await asyncio.wait_for(task, timeout=2.0)


async def test_stream_events_unknown_run_id_raises(tmp_path) -> None:
    state = _build_state(tmp_path)
    backend = InProcessRunBackend(state)
    try:
        async for _ in backend.stream_events("nope"):
            pass
    except LookupError:
        return
    raise AssertionError("expected LookupError for unknown run_id")


async def test_update_session_switches_the_mode(tmp_path, caplog) -> None:
    """The Telegram `/mode` tap lands in `state.chat_modes`, which the next
    turn reads (M280), and the daemon log records it for operators."""
    state = _build_state(tmp_path)
    backend = InProcessRunBackend(state)
    with caplog.at_level("INFO", logger="veles.channels.in_process_backend"):
        payload = await backend.update_session("sess-x", mode="planning")
    assert payload == {"session_id": "sess-x", "mode": "planning"}
    assert state.chat_mode("sess-x").mode == "planning"
    assert any("in-process session=sess-x mode=planning" in r.message for r in caplog.records)


async def test_update_session_default_switches_back(tmp_path) -> None:
    state = _build_state(tmp_path)
    state.set_chat_mode("sess-x", "writing")
    await InProcessRunBackend(state).update_session("sess-x", mode="default")
    assert state.chat_mode("sess-x").mode is None


async def test_update_session_rejects_an_unknown_mode(tmp_path) -> None:
    state = _build_state(tmp_path)
    with pytest.raises(ValueError, match="unknown mode"):
        await InProcessRunBackend(state).update_session("sess-x", mode="turbo")


async def test_get_session_reports_the_mode(tmp_path) -> None:
    state = _build_state(tmp_path)
    state.set_chat_mode("sess-x", "auto")
    backend = InProcessRunBackend(state)
    assert (await backend.get_session("sess-x"))["mode"] == "auto"
    assert (await backend.get_session("sess-unknown"))["mode"] == "default"


async def test_health_reports_daemon_provider(tmp_path) -> None:
    """In-process health surfaces `state.provider` so the gateway's
    /model picker resolves the daemon's fixed provider."""
    state = _build_state(tmp_path)
    state.provider = "ollama"
    backend = InProcessRunBackend(state)
    payload = await backend.health()
    assert payload["provider"] == "ollama"
    assert payload["status"] == "ok"


async def test_run_dream_runs_the_daemons_dream_runner(tmp_path) -> None:
    """Telegram /dream (M276) reaches the same runner the schedule uses."""
    from veles.core.dreaming import DreamResult

    calls: list[bool] = []

    class _Runner:
        async def force_run(self, *, include_consolidation: bool = True) -> DreamResult:
            calls.append(include_consolidation)
            return DreamResult(notes=["n1"])

    state = _build_state(tmp_path)
    state.dream_runner = _Runner()  # type: ignore[assignment]
    payload = await InProcessRunBackend(state).run_dream()
    assert calls == [True]
    assert payload["notes"] == ["n1"]
    assert payload["summary"]


async def test_run_dream_without_a_dream_runner_raises(tmp_path) -> None:
    state = _build_state(tmp_path)
    state.dream_runner = None
    with pytest.raises(RuntimeError, match="not enabled"):
        await InProcessRunBackend(state).run_dream()
