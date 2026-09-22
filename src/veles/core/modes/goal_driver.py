"""Drive a goal to an end without a person typing each turn (M276).

GoalMode is a one-turn-at-a-time state machine: every `run_turn` moves one
phase, and after CHECK it waits for the user to type `continue`
(`modes/goal.py`). That is right in the REPL and it is why `veles goal start`
never did anything: it wrote `goals/<id>.json` and printed "started goal …",
and no runtime ever read that id — GoalMode creates its own goal when it has
none. This module is the missing loop: it holds a goal, feeds GoalMode the
`continue` a user would have typed, and stops on any end state.

It is a loop *over* GoalMode, not a second machine: planning, executing,
checking, budgets and completion stay in `GoalMode` exactly as the REPL runs
them. Two things are added:

  - **Starting past the interview.** INTERVIEW and CONFIRM exist to get the
    objective and done condition out of a person and to check "did I get this
    right?". `start_goal` takes both as given — so a caller of `start_goal` +
    `drive_goal` vouches that the objective is complete. That holds for
    `veles goal start "…" --done-when "…"`; it does NOT hold for a sentence in a
    chat, which is why Telegram `/goal` keeps the interview.
  - **Knowing when to stop.** GoalMode already cancels on budget
    (`budget_exhausted`) and on `<infeasible>`, and completes on the advisor's
    `goal_reached`. The loop adds what only a loop needs: a stall guard (the
    goal made no progress for `max_stalled_turns` turns — e.g. PLAN keeps
    returning without calling `create_plan`) and a hard turn cap as a backstop.
    A goal that is paused from elsewhere (`veles goal pause <id>`) is noticed
    between turns and left paused.
"""

from __future__ import annotations

from dataclasses import dataclass

from veles.core.goal import Goal, GoalBudget, create_goal, read_goal, update_fsm
from veles.core.modes.base import ModeContext

_DEFAULT_MAX_STALLED_TURNS = 3


@dataclass(frozen=True, slots=True)
class GoalOutcome:
    """How a driven goal ended.

    `status` is the goal's own final status (`completed`, `cancelled`,
    `paused`, …) or one of the loop's stops: `stalled`, `turn_cap`, `missing`,
    `needs_interview`."""

    goal_id: str
    status: str
    reason: str
    turns: int

    @property
    def completed(self) -> bool:
        return self.status == "completed"


def start_goal(
    state_dir,
    *,
    objective: str,
    done_condition: str,
    scope: str = "",
    budget: GoalBudget | None = None,
) -> Goal:
    """Create a goal that begins at PLAN, with the interview's output supplied.

    PLAN reads only `interview_summary` (the confirmed statement of the goal)
    and CHECK reads `objective` + `done_condition`, so both are filled from the
    caller. A done condition is required: without one CHECK can never say
    `goal_reached`, and the loop would run until the budget ended it."""
    if not done_condition.strip():
        raise ValueError("a goal driven without an interview needs a done condition (--done-when)")
    goal = create_goal(
        state_dir,
        objective=objective,
        scope=scope,
        done_condition=done_condition,
        budget=budget,
    )
    summary = f"Objective: {goal.objective}\nDone when: {done_condition.strip()}"
    if scope.strip():
        summary += f"\nScope: {scope.strip()}"
    return update_fsm(state_dir, goal.id, phase="plan", interview_summary=summary)


def _progress_marker(goal: Goal) -> tuple:
    """Everything a turn that did something changes. Equal before and after a
    turn → the turn made no progress."""
    return (goal.current_phase, goal.steps_done, len(goal.progress), goal.plan_id, goal.status)


def _last_note(goal: Goal) -> str:
    return goal.progress[-1].description if goal.progress else ""


def drive_goal(
    ctx: ModeContext,
    goal_id: str,
    *,
    max_stalled_turns: int = _DEFAULT_MAX_STALLED_TURNS,
    max_turns: int | None = None,
) -> GoalOutcome:
    """Run GoalMode on `goal_id` until the goal ends or the loop has to stop.

    The caller vouches that the goal needs no interview (see the module
    docstring); a goal still in `interview`/`confirm` is refused rather than
    answered on the user's behalf."""
    from veles.core.modes import get_mode

    state_dir = ctx.project.state_dir
    mode = get_mode("goal")
    goal = read_goal(state_dir, goal_id)
    if goal is None:
        return GoalOutcome(goal_id, "missing", f"no goal {goal_id!r}", 0)
    cap = max_turns if max_turns is not None else goal.budget.max_steps * 3 + 10
    turns = 0
    stalled = 0

    while True:
        goal = read_goal(state_dir, goal_id)
        if goal is None:
            return GoalOutcome(goal_id, "missing", "the goal file disappeared", turns)
        if goal.status != "active":
            return GoalOutcome(goal_id, goal.status, _last_note(goal), turns)
        if goal.current_phase in ("interview", "confirm"):
            return GoalOutcome(
                goal_id,
                "needs_interview",
                f"goal is in {goal.current_phase}: it needs a person to answer, "
                "not a driver — continue it from the REPL",
                turns,
            )
        if turns >= cap:
            return GoalOutcome(goal_id, "turn_cap", f"stopped after {turns} turns", turns)

        before = _progress_marker(goal)
        # GoalMode clears these on completion/cancel; re-assert them each turn so
        # it never mistakes the driven goal for "no goal" and starts a new one.
        ctx.state.active_goal_id = goal_id
        ctx.state.mode = "goal"  # type: ignore[assignment]
        # An empty prompt lets each phase use its own cue ("Continue with the
        # plan.", "Execute the next step."); CHECK ignores it.
        mode.run_turn("", ctx)
        turns += 1

        after = read_goal(state_dir, goal_id)
        if after is not None and after.status == "active" and _progress_marker(after) == before:
            stalled += 1
            if stalled >= max_stalled_turns:
                return GoalOutcome(
                    goal_id,
                    "stalled",
                    f"no progress in {after.current_phase} for {stalled} turns",
                    turns,
                )
        else:
            stalled = 0


__all__ = ["GoalOutcome", "drive_goal", "start_goal"]
