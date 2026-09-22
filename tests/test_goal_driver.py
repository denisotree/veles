"""M276: `drive_goal` runs the real GoalMode to an end without a person typing.

The FSM itself is not reimplemented — these tests drive the production
`GoalMode` through `drive_goal`, with a fake agent factory (the planning agent
persists a plan exactly as the `create_plan` tool does) and a stubbed advisor
for CHECK, so no provider is touched. What is under test is the loop: it starts
past the interview, feeds `continue`, and stops on every end state — including
the ones only a loop can have (stall, turn cap, paused from elsewhere).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import patch

import pytest

from veles.core.agent import RunResult
from veles.core.goal import GoalBudget, pause, read_goal
from veles.core.modes import ModeContext
from veles.core.modes.goal_driver import drive_goal, start_goal
from veles.core.plan_artifact import create_plan
from veles.core.project import init_project
from veles.core.session_state import AppState

ADVISOR = "veles.core.tools.builtin.advisor.call_advisor"


@dataclass
class _Agent:
    project: object
    mode: str
    plan_steps: list[str] | None
    ran: list[str] = field(default_factory=list)

    def run(self, prompt, **_kw):
        self.ran.append(self.mode)
        if self.mode == "planning" and self.plan_steps is not None:
            # What the model's `create_plan` tool call persists.
            create_plan(self.project.state_dir, objective="obj", steps=self.plan_steps)
        return RunResult(text=f"{self.mode} done", iterations=1, stopped_reason="completed")


def _ctx(project, *, plan_steps=("write hello.txt",)):
    calls: list[str] = []

    def factory(state, *, mode_override=None, extra_system=None, **_kw):
        agent = _Agent(
            project, mode_override or state.mode, list(plan_steps) if plan_steps else None
        )
        calls.append(agent.mode)
        return agent

    lines: list[str] = []
    ctx = ModeContext(
        state=AppState(session_id=None, provider_name="stub", model="stub"),
        project=project,
        factory=factory,
        post=lambda ev: lines.append(getattr(ev, "text", "")),
        on_text=lambda _t: None,
        on_event=lambda _e: None,
    )
    return ctx, calls, lines


@pytest.fixture()
def project(tmp_path, monkeypatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    return init_project(tmp_path / "proj", name="proj", layout="bare")


def test_a_goal_runs_plan_execute_check_to_completion(project) -> None:
    goal = start_goal(project.state_dir, objective="say hi", done_condition="hello.txt exists")
    ctx, calls, _ = _ctx(project)
    with patch(ADVISOR, return_value='{"verdict": "goal_reached", "reason": "file exists"}'):
        outcome = drive_goal(ctx, goal.id)
    assert outcome.completed, outcome
    assert calls == ["planning", "writing"]  # PLAN, then EXECUTE; CHECK is the advisor
    assert outcome.turns == 3
    assert read_goal(project.state_dir, goal.id).status == "completed"


def test_the_interview_is_skipped_only_because_its_output_is_supplied(project) -> None:
    """PLAN reads `interview_summary`; CHECK reads objective + done condition."""
    goal = start_goal(project.state_dir, objective="say hi", done_condition="hello.txt exists")
    assert goal.current_phase == "plan"
    assert "say hi" in goal.interview_summary and "hello.txt exists" in goal.interview_summary


def test_a_done_condition_is_required(project) -> None:
    with pytest.raises(ValueError, match="done condition"):
        start_goal(project.state_dir, objective="say hi", done_condition="  ")


def test_the_budget_still_ends_a_goal_that_never_finishes(project) -> None:
    """Budgets are GoalMode's, not the driver's — this proves the driver lets
    them act instead of looping past them."""
    goal = start_goal(
        project.state_dir,
        objective="x",
        done_condition="y",
        budget=GoalBudget(max_steps=1),
    )
    ctx, _, _ = _ctx(project, plan_steps=["a", "b", "c"])
    with patch(ADVISOR, return_value='{"verdict": "step_ok_continue", "reason": "more"}'):
        outcome = drive_goal(ctx, goal.id)
    # GoalMode's budget guard ended it — not the loop's stall guard or turn cap.
    assert outcome.status == "cancelled", outcome
    assert outcome.turns < 10


def test_a_plan_phase_that_never_plans_is_stopped_as_stalled(project) -> None:
    """The model keeps answering PLAN without calling `create_plan`; GoalMode
    stays in PLAN by design, so only the loop can notice nothing is happening."""
    goal = start_goal(project.state_dir, objective="x", done_condition="y")
    ctx, calls, _ = _ctx(project, plan_steps=None)
    outcome = drive_goal(ctx, goal.id, max_stalled_turns=3)
    assert outcome.status == "stalled"
    assert calls == ["planning"] * 3
    assert read_goal(project.state_dir, goal.id).status == "active"  # left resumable


def test_a_goal_paused_from_elsewhere_stops_the_loop(project) -> None:
    goal = start_goal(project.state_dir, objective="x", done_condition="y")
    pause(project.state_dir, goal.id)  # `veles goal pause <id>` from another terminal
    ctx, calls, _ = _ctx(project)
    outcome = drive_goal(ctx, goal.id)
    assert outcome.status == "paused"
    assert calls == []


def test_a_goal_still_in_interview_is_refused_not_answered(project) -> None:
    from veles.core.goal import create_goal

    goal = create_goal(project.state_dir, objective="vague")  # phase = interview
    ctx, calls, _ = _ctx(project)
    outcome = drive_goal(ctx, goal.id)
    assert outcome.status == "needs_interview"
    assert calls == []


def test_a_driven_goal_resumes_where_it_stopped(project) -> None:
    """The state lives on disk (phase in goals/<id>.json, plan in
    plans/active/), so a second `drive_goal` — `veles goal resume` — continues
    from EXECUTE rather than planning again."""
    goal = start_goal(project.state_dir, objective="x", done_condition="y")
    ctx, _, _ = _ctx(project)
    drive_goal(ctx, goal.id, max_turns=1)  # PLAN only, then interrupted
    assert read_goal(project.state_dir, goal.id).current_phase == "execute"

    ctx2, calls2, _ = _ctx(project)
    with patch(ADVISOR, return_value='{"verdict": "goal_reached", "reason": "ok"}'):
        outcome = drive_goal(ctx2, goal.id)
    assert outcome.completed
    assert "planning" not in calls2  # no re-plan
