"""M76 — DreamRunner idle-timer + force_run trigger."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from veles.core.dream_runner import DreamRunner
from veles.core.project import Project, init_project
from veles.daemon.state import DaemonState


class _FakeRunHandle:
    def __init__(self, done: bool) -> None:
        self.done = type("E", (), {"is_set": lambda self_: done})()


def _make_state(project: Project, last_activity_at: float, runs_active: bool) -> DaemonState:
    from veles.core.memory import SessionStore
    from veles.daemon.auth import TokenStore

    state = DaemonState(
        project=project,
        store=SessionStore(":memory:"),
        token_store=TokenStore.load(project.state_dir / "tokens.json"),
        agent_factory=lambda sid: None,  # not invoked
        last_activity_at=last_activity_at,
    )
    if runs_active:
        state.runs["x"] = _FakeRunHandle(done=False)  # type: ignore[assignment]
    return state


@pytest.fixture()
def project(tmp_path: Path) -> Project:
    return init_project(tmp_path, name="dtest")


async def test_force_run_invokes_dream_cycle(project: Project) -> None:
    state = _make_state(project, last_activity_at=0.0, runs_active=False)
    runner = DreamRunner(
        project=project,
        state=state,
        provider_factory=None,  # no consolidation
    )
    result = await runner.force_run(include_consolidation=False)
    assert not result.skipped
    assert "dream" in result.summary()


async def test_maybe_run_skips_when_runs_active(project: Project) -> None:
    state = _make_state(project, last_activity_at=0.0, runs_active=True)
    runner = DreamRunner(
        project=project,
        state=state,
        provider_factory=None,
        idle_threshold_seconds=0.0,
        deep_interval_seconds=0.0,
    )
    await runner._maybe_run()
    assert runner._inflight is None


async def test_maybe_run_skips_when_not_idle(project: Project) -> None:
    state = _make_state(project, last_activity_at=time.time(), runs_active=False)
    runner = DreamRunner(
        project=project,
        state=state,
        provider_factory=None,
        idle_threshold_seconds=999.0,
        deep_interval_seconds=0.0,
    )
    await runner._maybe_run()
    assert runner._inflight is None


async def test_maybe_run_triggers_when_idle_and_due(project: Project) -> None:
    state = _make_state(project, last_activity_at=0.0, runs_active=False)
    runner = DreamRunner(
        project=project,
        state=state,
        provider_factory=None,  # consolidation will skip
        idle_threshold_seconds=0.0,
        deep_interval_seconds=0.0,
    )
    await runner._maybe_run()
    assert runner._inflight is not None
    await runner._inflight  # drain
    assert runner._last_result is not None


# ---- M214: proactive extraction cadence ----


class _FakeProvider:
    supports_tools = False

    def __init__(self, reply: str) -> None:
        self._reply = reply

    def create_message(self, messages, tools=None, *, model, max_tokens=4096):
        from veles.core.provider import ProviderResponse, TokenUsage

        return ProviderResponse(text=self._reply, tool_calls=[], usage=TokenUsage())


async def test_proactive_runs_without_idle_and_materialises(project: Project) -> None:
    """The proactive pass fires on its own short throttle and does NOT wait for
    the long idle gate — an event mentioned mid-session is still surfaced."""
    import datetime as _dt

    from veles.core.curator_state import load as _load_state
    from veles.core.provider import Message
    from veles.core.tasks_store import TasksStore

    now = time.time()
    when = _dt.datetime.fromtimestamp(now + 3600, tz=_dt.UTC).isoformat()
    reply = f'[{{"title": "BC GAME live", "when": "{when}"}}]'

    # NOT idle (last_activity_at=now) and no deep dream possible → only the
    # proactive branch can fire.
    state = _make_state(project, last_activity_at=now, runs_active=False)
    runner = DreamRunner(
        project=project,
        state=state,
        provider_factory=lambda: _FakeProvider(reply),
        consolidation_model="stub",
        proactive_history_loader=lambda: [("s1", [Message(role="user", content="BC GAME at 1am")])],
        idle_threshold_seconds=999.0,  # would block a deep dream
        proactive_interval_seconds=0.0,  # due immediately
    )
    await runner._maybe_run()
    assert runner._inflight is not None
    await runner._inflight  # drain the proactive task

    store = TasksStore(project.memory_db_path)
    try:
        dream_tasks = store.list_tasks(state=None, source="dream")
    finally:
        store.close()
    assert [t.title for t in dream_tasks] == ["BC GAME live"]
    # throttle advanced so the next tick won't immediately re-run
    assert _load_state(project.state_dir / "curator.state.json").last_proactive_at >= now


async def test_proactive_skipped_without_provider(project: Project) -> None:
    state = _make_state(project, last_activity_at=time.time(), runs_active=False)
    runner = DreamRunner(
        project=project,
        state=state,
        provider_factory=None,  # no provider → no proactive pass
        proactive_history_loader=lambda: [],
        idle_threshold_seconds=999.0,
        proactive_interval_seconds=0.0,
    )
    await runner._maybe_run()
    assert runner._inflight is None  # neither proactive nor deep dream fires


async def test_status_reports_idle_thresholds(project: Project) -> None:
    state = _make_state(project, last_activity_at=0.0, runs_active=False)
    runner = DreamRunner(
        project=project,
        state=state,
        provider_factory=None,
        idle_threshold_seconds=42.0,
        deep_interval_seconds=4242.0,
    )
    s = runner.status()
    assert s["idle_threshold"] == 42.0
    assert s["deep_interval"] == 4242.0
    assert s["enabled"] is False


async def test_start_stop_idempotent(project: Project) -> None:
    state = _make_state(project, last_activity_at=0.0, runs_active=False)
    runner = DreamRunner(
        project=project,
        state=state,
        provider_factory=None,
        check_interval_seconds=10.0,
        idle_threshold_seconds=999.0,  # never trigger during test
        deep_interval_seconds=999.0,
    )
    await runner.start()
    await runner.start()  # second call should be a no-op
    await runner.stop()
    await runner.stop()  # idempotent
