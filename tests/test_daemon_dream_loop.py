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
