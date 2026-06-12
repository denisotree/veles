"""GoalMode — finite state machine driving INTERVIEW → CONFIRM → PLAN →
EXECUTE → CHECK → DONE with cooperative interrupts (one user prompt =
one phase transition).

We exercise each phase transition with a fake `Agent` factory and a
stubbed `call_advisor` so no provider is touched. The Goal artifact is
the system-of-record: after each handler we re-read it from disk to
confirm the FSM phase advanced correctly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import patch

import pytest

from tests.conftest import FakeAgent as _FakeAgent
from veles.core.agent import RunResult
from veles.core.context import reset_active_project, set_active_project
from veles.core.goal import (
    Goal,
    create_goal,
    read_goal,
    update_fsm,
)
from veles.core.modes import GoalMode, ModeContext
from veles.core.modes.goal import (
    _classify_confirm_reply,
    parse_check_verdict,
    parse_infeasible_marker,
    parse_ready_marker,
)
from veles.core.plan_artifact import active_dir, create_plan, list_active
from veles.core.project import init_project
from veles.tui.messages import SystemLine, TurnDone
from veles.tui.state import AppState


# ---------- pure parser tests ----------


def test_parse_ready_marker_returns_inner_summary() -> None:
    assert parse_ready_marker("<ready>do X by Y</ready>") == "do X by Y"


def test_parse_ready_marker_handles_multiline() -> None:
    raw = "asking...\n<ready>\nlong\nsummary\n</ready>\nbye"
    assert parse_ready_marker(raw) == "long\nsummary"


def test_parse_ready_marker_returns_none_when_absent() -> None:
    assert parse_ready_marker("plain text without marker") is None


def test_parse_infeasible_marker_returns_reason() -> None:
    assert parse_infeasible_marker("<infeasible>needs a GPU</infeasible>") == "needs a GPU"


def test_parse_check_verdict_happy_path() -> None:
    raw = '{"verdict": "step_ok_continue", "reason": "looks good"}'
    assert parse_check_verdict(raw) == ("step_ok_continue", "looks good")


def test_parse_check_verdict_strips_code_fences() -> None:
    raw = '```json\n{"verdict": "goal_reached", "reason": "done"}\n```'
    assert parse_check_verdict(raw) == ("goal_reached", "done")


def test_parse_check_verdict_defaults_off_track_on_garbage() -> None:
    verdict, reason = parse_check_verdict("not json at all")
    assert verdict == "step_off_track"
    assert "parse" in reason.lower()


def test_parse_check_verdict_defaults_off_track_on_unknown_verdict() -> None:
    verdict, reason = parse_check_verdict('{"verdict": "blah", "reason": "x"}')
    assert verdict == "step_off_track"
    assert "blah" in reason


@pytest.mark.parametrize(
    "prompt,expected",
    [
        ("yes", "yes"),
        ("YES!", "yes"),
        ("да", "yes"),
        ("ok", "yes"),
        ("cancel", "cancel"),
        ("отменить", "cancel"),
        ("no, actually ...", "no"),
        ("change scope to Z", "no"),
        ("", "no"),
    ],
)
def test_classify_confirm_reply(prompt: str, expected: str) -> None:
    assert _classify_confirm_reply(prompt) == expected


# ---------- FSM tests ----------


@dataclass
class _Recorder:
    state: AppState
    project: object
    next_result: RunResult
    posted: list[Any] = field(default_factory=list)
    factory_calls: list[dict] = field(default_factory=list)
    next_agent: _FakeAgent | None = None

    def make_ctx(self) -> ModeContext:
        def factory(state: AppState, **kwargs) -> _FakeAgent:
            self.factory_calls.append(kwargs)
            agent = _FakeAgent(
                result=self.next_result,
                captured_extra_system=kwargs.get("extra_system"),
            )
            self.next_agent = agent
            return agent

        return ModeContext(
            state=self.state,
            project=self.project,  # type: ignore[arg-type]
            factory=factory,  # type: ignore[arg-type]
            post=self.posted.append,
            on_text=lambda _t: None,
            on_event=lambda _e: None,
        )


@pytest.fixture
def project(tmp_path):
    return init_project(tmp_path / "proj", name="proj")


@pytest.fixture
def state() -> AppState:
    return AppState(
        session_id=None,
        provider_name="stub",
        model="m",
        mode="goal",
        active_goal_id=None,
    )


def _last_system_line(posted: list[Any]) -> str:
    for msg in reversed(posted):
        if isinstance(msg, SystemLine):
            return msg.text
    return ""


# --- bootstrap ---


def test_goal_first_turn_bootstraps_artifact_in_interview(project, state) -> None:
    """No `active_goal_id` → GoalMode creates a fresh Goal in `interview`
    phase, records the id on AppState, and routes the prompt to the
    interview handler."""
    token = set_active_project(project)
    try:
        rec = _Recorder(
            state=state,
            project=project,
            next_result=RunResult(text="just one Q?", iterations=1, session_id="s1"),
        )
        GoalMode().run_turn("add a dark theme", rec.make_ctx())
    finally:
        reset_active_project(token)

    assert state.active_goal_id is not None
    goal = read_goal(project.state_dir, state.active_goal_id)
    assert goal is not None
    assert goal.current_phase == "interview"
    assert state.last_mode_in_session == "goal"


# --- interview phase ---


def test_goal_interview_to_confirm_on_ready_marker(project, state) -> None:
    """Model emits `<ready>summary</ready>` → FSM advances to `confirm`
    and the summary is persisted on the Goal."""
    token = set_active_project(project)
    try:
        goal = create_goal(
            project.state_dir, objective="placeholder", done_condition=""
        )
        state.active_goal_id = goal.id
        update_fsm(project.state_dir, goal.id, phase="interview")

        rec = _Recorder(
            state=state,
            project=project,
            next_result=RunResult(
                text="ok, <ready>Add dark theme to TUI; done when /theme dark works.</ready>",
                iterations=1,
                session_id="s1",
            ),
        )
        GoalMode().run_turn("yes that's right", rec.make_ctx())
    finally:
        reset_active_project(token)

    goal = read_goal(project.state_dir, state.active_goal_id)
    assert goal.current_phase == "confirm"
    assert "dark theme" in goal.interview_summary


def test_goal_interview_uses_writing_registry_and_interview_prompt(
    project, state
) -> None:
    token = set_active_project(project)
    try:
        goal = create_goal(project.state_dir, objective="x", done_condition="")
        state.active_goal_id = goal.id
        rec = _Recorder(
            state=state,
            project=project,
            next_result=RunResult(text="question?", iterations=1, session_id="s1"),
        )
        GoalMode().run_turn("hi", rec.make_ctx())
    finally:
        reset_active_project(token)

    kwargs = rec.factory_calls[0]
    assert kwargs.get("mode_override") == "writing"
    assert "INTERVIEW" in (kwargs.get("extra_system") or "")


# --- confirm phase ---


def test_goal_confirm_first_turn_emits_confirmation_line(project, state) -> None:
    """When entering CONFIRM (prompt empty), GoalMode emits the
    localized confirmation line via direct ChatDelta + TurnDone."""
    from veles.tui.messages import ChatDelta

    token = set_active_project(project)
    try:
        goal = create_goal(project.state_dir, objective="x", done_condition="")
        state.active_goal_id = goal.id
        update_fsm(
            project.state_dir,
            goal.id,
            phase="confirm",
            interview_summary="Add dark theme.",
        )
        rec = _Recorder(
            state=state,
            project=project,
            next_result=RunResult(text="", iterations=0, stopped_reason="synthetic"),
        )
        GoalMode().run_turn("", rec.make_ctx())
    finally:
        reset_active_project(token)

    chat_deltas = [m for m in rec.posted if isinstance(m, ChatDelta)]
    assert chat_deltas, "CONFIRM phase must emit a chat-visible confirmation line"
    from veles.core.i18n import t

    body = chat_deltas[0].text
    assert t("goal.confirm_line", summary="Add dark theme.") in body
    assert t("goal.confirm_actions") in body


def test_goal_confirm_yes_advances_to_plan(project, state) -> None:
    token = set_active_project(project)
    try:
        goal = create_goal(project.state_dir, objective="x", done_condition="")
        state.active_goal_id = goal.id
        update_fsm(
            project.state_dir,
            goal.id,
            phase="confirm",
            interview_summary="Add dark theme",
        )
        rec = _Recorder(
            state=state,
            project=project,
            next_result=RunResult(text="", iterations=0, stopped_reason="synthetic"),
        )
        GoalMode().run_turn("yes", rec.make_ctx())
    finally:
        reset_active_project(token)

    goal = read_goal(project.state_dir, state.active_goal_id)
    assert goal.current_phase == "plan"


def test_goal_confirm_cancel_terminates_and_flips_to_auto(project, state) -> None:
    token = set_active_project(project)
    try:
        goal = create_goal(project.state_dir, objective="x", done_condition="")
        state.active_goal_id = goal.id
        update_fsm(
            project.state_dir,
            goal.id,
            phase="confirm",
            interview_summary="Add dark theme",
        )
        rec = _Recorder(
            state=state,
            project=project,
            next_result=RunResult(text="", iterations=0, stopped_reason="synthetic"),
        )
        GoalMode().run_turn("cancel", rec.make_ctx())
    finally:
        reset_active_project(token)

    goal_after = read_goal(project.state_dir, goal.id)
    assert goal_after.status == "cancelled"
    assert state.active_goal_id is None
    assert state.mode == "auto"


def test_goal_confirm_no_returns_to_interview_with_edits(project, state) -> None:
    token = set_active_project(project)
    try:
        goal = create_goal(project.state_dir, objective="x", done_condition="")
        state.active_goal_id = goal.id
        update_fsm(
            project.state_dir,
            goal.id,
            phase="confirm",
            interview_summary="Add dark theme",
        )
        rec = _Recorder(
            state=state,
            project=project,
            next_result=RunResult(text="more Q?", iterations=1, session_id="s1"),
        )
        GoalMode().run_turn("also restrict to TUI only", rec.make_ctx())
    finally:
        reset_active_project(token)

    goal_after = read_goal(project.state_dir, state.active_goal_id)
    assert goal_after.current_phase == "interview"
    assert "restrict to TUI only" in goal_after.interview_summary


# --- plan phase ---


def test_goal_plan_infeasible_cancels(project, state) -> None:
    token = set_active_project(project)
    try:
        goal = create_goal(project.state_dir, objective="x", done_condition="")
        state.active_goal_id = goal.id
        update_fsm(project.state_dir, goal.id, phase="plan", interview_summary="x")
        rec = _Recorder(
            state=state,
            project=project,
            next_result=RunResult(
                text="<infeasible>requires hardware we don't have</infeasible>",
                iterations=1,
                session_id="s1",
            ),
        )
        GoalMode().run_turn("plan it", rec.make_ctx())
    finally:
        reset_active_project(token)

    goal_after = read_goal(project.state_dir, goal.id)
    assert goal_after.status == "cancelled"
    assert state.active_goal_id is None
    assert state.mode == "auto"


def test_goal_plan_advances_to_execute_when_plan_persisted(project, state) -> None:
    """The PLAN phase routes through the planning toolset. We simulate
    a successful `create_plan` tool call by directly writing an active
    plan, then run the PLAN handler — it should detect the plan and
    advance to EXECUTE."""
    token = set_active_project(project)
    try:
        goal = create_goal(project.state_dir, objective="x", done_condition="")
        state.active_goal_id = goal.id
        update_fsm(project.state_dir, goal.id, phase="plan", interview_summary="x")
        plan = create_plan(
            project.state_dir,
            objective="ship dark theme",
            steps=["step1", "step2"],
        )
        rec = _Recorder(
            state=state,
            project=project,
            next_result=RunResult(
                text="plan created: " + plan.id,
                iterations=1,
                session_id="s1",
            ),
        )
        GoalMode().run_turn("plan", rec.make_ctx())
    finally:
        reset_active_project(token)

    goal_after = read_goal(project.state_dir, goal.id)
    assert goal_after.current_phase == "execute"
    assert goal_after.plan_id == plan.id


def test_goal_plan_phase_uses_planning_registry(project, state) -> None:
    token = set_active_project(project)
    try:
        goal = create_goal(project.state_dir, objective="x", done_condition="")
        state.active_goal_id = goal.id
        update_fsm(project.state_dir, goal.id, phase="plan", interview_summary="x")
        rec = _Recorder(
            state=state,
            project=project,
            next_result=RunResult(
                text="<infeasible>nope</infeasible>", iterations=1, session_id="s1"
            ),
        )
        GoalMode().run_turn("p", rec.make_ctx())
    finally:
        reset_active_project(token)

    kwargs = rec.factory_calls[0]
    assert kwargs.get("mode_override") == "planning"


# --- execute phase ---


def test_goal_execute_runs_one_step_then_check(project, state) -> None:
    token = set_active_project(project)
    try:
        goal = create_goal(project.state_dir, objective="x", done_condition="")
        plan = create_plan(
            project.state_dir,
            objective="ship dark theme",
            steps=["wire CSS variables", "update theme picker"],
        )
        state.active_goal_id = goal.id
        update_fsm(
            project.state_dir,
            goal.id,
            phase="execute",
            plan_id=plan.id,
        )
        rec = _Recorder(
            state=state,
            project=project,
            next_result=RunResult(
                text="wired variables", iterations=2, session_id="s1"
            ),
        )
        GoalMode().run_turn("continue", rec.make_ctx())
    finally:
        reset_active_project(token)

    goal_after = read_goal(project.state_dir, goal.id)
    assert goal_after.current_phase == "check"
    # One checkpoint recorded for the executed step.
    assert any(
        "step 1/2" in cp.description for cp in goal_after.progress
    )


def test_goal_execute_via_manager_when_manager_mode_on(project, state, monkeypatch) -> None:
    """M122c: with VELES_MANAGER_MODE on, the EXECUTE step is decomposed into
    explorer→writer workers (2 factory calls) instead of a single agent turn;
    the FSM still advances to CHECK and records the step."""
    monkeypatch.setenv("VELES_MANAGER_MODE", "1")
    token = set_active_project(project)
    try:
        goal = create_goal(project.state_dir, objective="x", done_condition="")
        plan = create_plan(
            project.state_dir,
            objective="ship dark theme",
            steps=["wire CSS variables", "update theme picker"],
        )
        state.active_goal_id = goal.id
        update_fsm(project.state_dir, goal.id, phase="execute", plan_id=plan.id)
        rec = _Recorder(
            state=state,
            project=project,
            next_result=RunResult(text="did the work", iterations=1, session_id="s1"),
        )
        GoalMode().run_turn("continue", rec.make_ctx())
    finally:
        reset_active_project(token)

    # Explorer + writer → two factory invocations (vs one for the direct path).
    assert len(rec.factory_calls) == 2
    goal_after = read_goal(project.state_dir, goal.id)
    assert goal_after.current_phase == "check"
    assert any("step 1/2" in cp.description for cp in goal_after.progress)
    assert any("manager-spawn" in _txt(m) for m in rec.posted)


def _txt(msg) -> str:
    return getattr(msg, "text", "") or ""


# --- check phase ---


def test_goal_check_goal_reached_completes(project, state) -> None:
    token = set_active_project(project)
    try:
        goal = create_goal(
            project.state_dir, objective="x", done_condition="all green"
        )
        plan = create_plan(
            project.state_dir, objective="ship dark theme", steps=["a", "b"]
        )
        state.active_goal_id = goal.id
        update_fsm(
            project.state_dir, goal.id, phase="check", plan_id=plan.id
        )

        rec = _Recorder(
            state=state,
            project=project,
            next_result=RunResult(
                text="", iterations=0, stopped_reason="synthetic"
            ),
        )
        with patch(
            "veles.core.tools.builtin.advisor.call_advisor",
            return_value='{"verdict": "goal_reached", "reason": "all green"}',
        ):
            GoalMode().run_turn("continue", rec.make_ctx())
    finally:
        reset_active_project(token)

    goal_after = read_goal(project.state_dir, goal.id)
    assert goal_after.status == "completed"
    assert state.active_goal_id is None
    assert state.mode == "auto"


def test_goal_check_step_ok_continue_loops_to_execute(project, state) -> None:
    token = set_active_project(project)
    try:
        goal = create_goal(project.state_dir, objective="x", done_condition="")
        plan = create_plan(
            project.state_dir, objective="ship", steps=["a", "b"]
        )
        state.active_goal_id = goal.id
        update_fsm(project.state_dir, goal.id, phase="check", plan_id=plan.id)
        rec = _Recorder(
            state=state,
            project=project,
            next_result=RunResult(text="", iterations=0, stopped_reason="synthetic"),
        )
        with patch(
            "veles.core.tools.builtin.advisor.call_advisor",
            return_value='{"verdict": "step_ok_continue", "reason": "progress"}',
        ):
            GoalMode().run_turn("continue", rec.make_ctx())
    finally:
        reset_active_project(token)

    goal_after = read_goal(project.state_dir, goal.id)
    assert goal_after.current_phase == "execute"
    assert goal_after.status == "active"


def test_goal_check_step_off_track_reroutes_to_plan(project, state) -> None:
    token = set_active_project(project)
    try:
        goal = create_goal(project.state_dir, objective="x", done_condition="")
        plan = create_plan(project.state_dir, objective="ship", steps=["a"])
        state.active_goal_id = goal.id
        update_fsm(project.state_dir, goal.id, phase="check", plan_id=plan.id)
        rec = _Recorder(
            state=state,
            project=project,
            next_result=RunResult(text="", iterations=0, stopped_reason="synthetic"),
        )
        with patch(
            "veles.core.tools.builtin.advisor.call_advisor",
            return_value='{"verdict": "step_off_track", "reason": "wrong direction"}',
        ):
            GoalMode().run_turn("continue", rec.make_ctx())
    finally:
        reset_active_project(token)

    goal_after = read_goal(project.state_dir, goal.id)
    assert goal_after.current_phase == "plan"


def test_goal_check_unparseable_advisor_defaults_to_off_track(project, state) -> None:
    """Malformed advisor JSON must not silently advance — it should
    re-plan (the safer default)."""
    token = set_active_project(project)
    try:
        goal = create_goal(project.state_dir, objective="x", done_condition="")
        plan = create_plan(project.state_dir, objective="ship", steps=["a"])
        state.active_goal_id = goal.id
        update_fsm(project.state_dir, goal.id, phase="check", plan_id=plan.id)
        rec = _Recorder(
            state=state,
            project=project,
            next_result=RunResult(text="", iterations=0, stopped_reason="synthetic"),
        )
        with patch(
            "veles.core.tools.builtin.advisor.call_advisor",
            return_value="totally not json",
        ):
            GoalMode().run_turn("continue", rec.make_ctx())
    finally:
        reset_active_project(token)

    goal_after = read_goal(project.state_dir, goal.id)
    assert goal_after.current_phase == "plan"


# --- budget guard ---


def test_goal_budget_exhaustion_cancels(project, state) -> None:
    token = set_active_project(project)
    try:
        from veles.core.goal import GoalBudget

        # Tight budget: 1 step max, then exhausted.
        goal = create_goal(
            project.state_dir,
            objective="x",
            done_condition="",
            budget=GoalBudget(max_steps=1),
        )
        # Pre-bump the counter so budget_exhausted fires on entry to plan.
        from veles.core.goal import append_checkpoint

        append_checkpoint(
            project.state_dir,
            goal.id,
            description="prior step",
            advance_step=True,
        )
        state.active_goal_id = goal.id
        update_fsm(project.state_dir, goal.id, phase="plan")
        rec = _Recorder(
            state=state,
            project=project,
            next_result=RunResult(text="", iterations=0, stopped_reason="synthetic"),
        )
        GoalMode().run_turn("p", rec.make_ctx())
    finally:
        reset_active_project(token)

    goal_after = read_goal(project.state_dir, goal.id)
    assert goal_after.status == "cancelled"
    assert state.active_goal_id is None
    assert state.mode == "auto"


# --- persistence / backward compat ---


def test_goal_from_dict_supplies_defaults_for_old_files(project) -> None:
    """JSON files written before GoalMode existed lack `current_phase` /
    `plan_id` / `interview_summary`. `_from_dict` must fill safe
    defaults rather than KeyError."""
    import json

    goals = project.state_dir / "goals"
    goals.mkdir(parents=True, exist_ok=True)
    (goals / "g-old.json").write_text(
        json.dumps(
            {
                "id": "g-old",
                "objective": "legacy goal",
                "status": "active",
                "budget": {"max_steps": 30, "max_cost_usd": 5.0, "max_wall_time_s": 3600},
                "progress": [],
                "steps_done": 0,
                "cost_spent_usd": 0.0,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    goal = read_goal(project.state_dir, "g-old")
    assert goal is not None
    assert goal.current_phase == "interview"
    assert goal.plan_id is None
    assert goal.interview_summary == ""


# Silence ruff F401 for `active_dir`, `list_active` — keeping the imports
# at file top for readability if future tests want them.
_ = active_dir, list_active, Goal
