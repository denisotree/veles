"""Goal-like loop primitives (Tier δ extension, prev. deferred).

A *goal* is a long-horizon objective with a measurable done condition and
a budget — distinct from a plan (`core/plan_artifact.py` will land this
session) which is the *how*. Best-practices §planning-and-goals: «plan:
how to approach the work; goal: what state should eventually be true».

This module is *opt-in*. The agent loop is unchanged when no goal is
attached. CLI exposes `veles goal {list,show,start,step,done,pause,resume}`
for the user-facing surface. A goal lives as a single JSON file per
goal_id under `<project>/.veles/goals/<id>.json` so external tools
(jq, cron, dashboards) can read state without a SQLite handle.

Forbidden: goal-loop wrapping `agent.run()` automatically. The user
explicitly attaches a goal_id to a run via `veles run --goal <id>` or
calls `GoalLoop.step(goal_id, agent)` from a script. This keeps the
short-task path (one-shot `veles run`) free of goal-loop machinery
overhead.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

GOALS_DIRNAME = "goals"

GoalStatus = Literal[
    "active",
    "paused",
    "completed",
    "blocked",
    "cancelled",
]

# GoalMode FSM phases (M78 extension). Stored on the Goal so a TUI
# restart picks up exactly where the previous session left off.
#
#   interview → confirm   (model emits `<ready>summary</ready>`)
#   confirm   → plan      (user confirms understanding)
#   confirm   → interview (user rejects / edits)
#   plan      → execute   (`create_plan` ran successfully)
#   plan      → abandoned (model emits `<infeasible>`)
#   execute   → check     (one EXECUTE step completed)
#   check     → execute   (advisor says step_ok_continue)
#   check     → plan      (advisor says step_off_track → re-plan)
#   check     → done      (advisor says goal_reached)
GoalPhase = Literal[
    "interview",
    "confirm",
    "plan",
    "execute",
    "check",
    "done",
]


@dataclass(slots=True)
class GoalBudget:
    """Hard caps. Driver stops when any is exceeded."""

    max_steps: int = 30
    max_cost_usd: float = 5.0
    max_wall_time_s: int = 3600


@dataclass(slots=True)
class CheckpointEntry:
    """One unit of progress. Append-only inside the Goal."""

    ts: str
    description: str
    evidence_ref: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Goal:
    """Durable objective. Persists as JSON."""

    id: str
    objective: str
    scope: str = ""
    done_condition: str = ""
    status: GoalStatus = "active"
    budget: GoalBudget = field(default_factory=GoalBudget)
    forbidden_actions: list[str] = field(default_factory=list)
    approval_required_for: list[str] = field(default_factory=list)
    progress: list[CheckpointEntry] = field(default_factory=list)
    steps_done: int = 0
    cost_spent_usd: float = 0.0
    created_at: str = ""
    updated_at: str = ""
    completed_at: str | None = None
    # GoalMode FSM state (TUI Shift+Tab → goal). Optional: a goal
    # created via `veles goal start` (CLI) never enters GoalMode and
    # these stay at their defaults. `_from_dict` round-trips with safe
    # fallbacks so old JSON files load unchanged.
    current_phase: GoalPhase = "interview"
    plan_id: str | None = None
    interview_summary: str = ""


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def goals_dir(state_dir: Path) -> Path:
    return state_dir / GOALS_DIRNAME


def _goal_path(state_dir: Path, goal_id: str) -> Path:
    return goals_dir(state_dir) / f"{goal_id}.json"


def create_goal(
    state_dir: Path,
    *,
    objective: str,
    scope: str = "",
    done_condition: str = "",
    budget: GoalBudget | None = None,
    forbidden_actions: list[str] | None = None,
    approval_required_for: list[str] | None = None,
) -> Goal:
    """Persist a new Goal and return it. Raises ValueError on empty objective."""
    if not objective.strip():
        raise ValueError("goal objective cannot be empty")
    now = _now_iso()
    goal = Goal(
        id=uuid.uuid4().hex[:12],
        objective=objective.strip(),
        scope=scope,
        done_condition=done_condition,
        budget=budget or GoalBudget(),
        forbidden_actions=list(forbidden_actions or []),
        approval_required_for=list(approval_required_for or []),
        created_at=now,
        updated_at=now,
    )
    _write(state_dir, goal)
    return goal


def read_goal(state_dir: Path, goal_id: str) -> Goal | None:
    path = _goal_path(state_dir, goal_id)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return _from_dict(raw)


def list_goals(state_dir: Path, *, status: GoalStatus | None = None) -> list[Goal]:
    """Return all goals, optionally filtered by status. Sorted by updated_at desc."""
    d = goals_dir(state_dir)
    if not d.exists():
        return []
    goals: list[Goal] = []
    for f in d.iterdir():
        if not f.is_file() or f.suffix != ".json":
            continue
        try:
            raw = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        g = _from_dict(raw)
        if status is None or g.status == status:
            goals.append(g)
    goals.sort(key=lambda g: g.updated_at, reverse=True)
    return goals


def append_checkpoint(
    state_dir: Path,
    goal_id: str,
    description: str,
    *,
    evidence_ref: str | None = None,
    metrics: dict[str, Any] | None = None,
    advance_step: bool = True,
    cost_usd: float = 0.0,
) -> Goal:
    """Add a checkpoint entry to the goal and persist.

    `advance_step=True` increments `steps_done` (the budget counter);
    pass False for purely-informational checkpoints (e.g. progress notes
    that aren't bounded by max_steps).
    """
    goal = _require(state_dir, goal_id)
    if goal.status not in ("active", "paused"):
        raise ValueError(f"cannot append to goal in status {goal.status!r}")
    entry = CheckpointEntry(
        ts=_now_iso(),
        description=description,
        evidence_ref=evidence_ref,
        metrics=dict(metrics or {}),
    )
    goal.progress.append(entry)
    if advance_step:
        goal.steps_done += 1
    goal.cost_spent_usd += cost_usd
    goal.updated_at = _now_iso()
    _write(state_dir, goal)
    return goal


def pause(state_dir: Path, goal_id: str) -> Goal:
    return _transition(state_dir, goal_id, target="paused", from_={"active"})


def resume(state_dir: Path, goal_id: str) -> Goal:
    return _transition(state_dir, goal_id, target="active", from_={"paused"})


def complete(state_dir: Path, goal_id: str, *, evidence: str | None = None) -> Goal:
    """Mark goal as completed; records the final evidence as a checkpoint."""
    goal = _require(state_dir, goal_id)
    if goal.status not in ("active", "paused"):
        raise ValueError(f"goal {goal_id} cannot be completed from status {goal.status!r}")
    if evidence:
        goal.progress.append(
            CheckpointEntry(
                ts=_now_iso(),
                description=f"done: {evidence}",
            )
        )
    goal.status = "completed"
    goal.completed_at = _now_iso()
    goal.updated_at = goal.completed_at
    _write(state_dir, goal)
    return goal


def cancel(state_dir: Path, goal_id: str, *, reason: str = "") -> Goal:
    goal = _require(state_dir, goal_id)
    if goal.status == "completed":
        raise ValueError(f"goal {goal_id} is already completed")
    if reason:
        goal.progress.append(CheckpointEntry(ts=_now_iso(), description=f"cancelled: {reason}"))
    goal.status = "cancelled"
    goal.updated_at = _now_iso()
    _write(state_dir, goal)
    return goal


def update_fsm(
    state_dir: Path,
    goal_id: str,
    *,
    phase: GoalPhase | None = None,
    plan_id: str | None = None,
    interview_summary: str | None = None,
) -> Goal:
    """Patch the GoalMode-FSM fields on a Goal. Only the kwargs passed
    are written; everything else is preserved. `plan_id` accepts an
    explicit `None` to clear via the sentinel `""` (use `clear_plan_id`
    for clarity instead). Returns the updated Goal."""
    goal = _require(state_dir, goal_id)
    if phase is not None:
        goal.current_phase = phase
    if plan_id is not None:
        goal.plan_id = plan_id or None
    if interview_summary is not None:
        goal.interview_summary = interview_summary
    goal.updated_at = _now_iso()
    _write(state_dir, goal)
    return goal


def budget_exhausted(goal: Goal) -> str | None:
    """Return a non-None reason when any budget is exceeded; None otherwise."""
    if goal.steps_done >= goal.budget.max_steps:
        return f"max_steps reached ({goal.steps_done}/{goal.budget.max_steps})"
    if goal.cost_spent_usd >= goal.budget.max_cost_usd:
        return f"max_cost reached (${goal.cost_spent_usd:.2f}/${goal.budget.max_cost_usd:.2f})"
    if goal.created_at:
        elapsed = _seconds_since_iso(goal.created_at)
        if elapsed >= goal.budget.max_wall_time_s:
            return f"max_wall_time reached ({elapsed}s/{goal.budget.max_wall_time_s}s)"
    return None


def render_system_block(goal: Goal) -> str:
    """Render `<goal>...</goal>` block for system-prompt injection.

    The agent loop opts in via `Agent(goal_id=...)`. Block is brief on
    purpose: objective + done_condition + budget summary; forbidden /
    approval lists go into the same block only when non-empty.
    """
    lines = [
        f'<goal id="{goal.id}" status="{goal.status}">',
        f"Objective: {goal.objective}",
    ]
    if goal.done_condition:
        lines.append(f"Done when: {goal.done_condition}")
    lines.append(
        f"Budget: {goal.steps_done}/{goal.budget.max_steps} steps, "
        f"${goal.cost_spent_usd:.2f}/${goal.budget.max_cost_usd:.2f}"
    )
    if goal.forbidden_actions:
        lines.append("Forbidden actions: " + ", ".join(goal.forbidden_actions))
    if goal.approval_required_for:
        lines.append("Approval required for: " + ", ".join(goal.approval_required_for))
    lines.append("</goal>")
    return "\n".join(lines)


# ---------- internals ----------


def _require(state_dir: Path, goal_id: str) -> Goal:
    g = read_goal(state_dir, goal_id)
    if g is None:
        raise KeyError(f"no goal with id {goal_id!r} at {state_dir}")
    return g


def _transition(
    state_dir: Path,
    goal_id: str,
    *,
    target: GoalStatus,
    from_: set[GoalStatus],
) -> Goal:
    goal = _require(state_dir, goal_id)
    if goal.status not in from_:
        raise ValueError(
            f"cannot transition goal {goal_id} from {goal.status!r} to {target!r}"
        )
    goal.status = target
    goal.updated_at = _now_iso()
    _write(state_dir, goal)
    return goal


def _write(state_dir: Path, goal: Goal) -> None:
    path = _goal_path(state_dir, goal.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(goal), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _from_dict(raw: dict[str, Any]) -> Goal:
    budget_raw = raw.get("budget") or {}
    budget = GoalBudget(
        max_steps=int(budget_raw.get("max_steps", 30)),
        max_cost_usd=float(budget_raw.get("max_cost_usd", 5.0)),
        max_wall_time_s=int(budget_raw.get("max_wall_time_s", 3600)),
    )
    progress = [
        CheckpointEntry(
            ts=str(p.get("ts", "")),
            description=str(p.get("description", "")),
            evidence_ref=p.get("evidence_ref"),
            metrics=dict(p.get("metrics") or {}),
        )
        for p in raw.get("progress") or []
        if isinstance(p, dict)
    ]
    return Goal(
        id=str(raw["id"]),
        objective=str(raw["objective"]),
        scope=str(raw.get("scope", "")),
        done_condition=str(raw.get("done_condition", "")),
        status=raw.get("status", "active"),
        budget=budget,
        forbidden_actions=list(raw.get("forbidden_actions") or []),
        approval_required_for=list(raw.get("approval_required_for") or []),
        progress=progress,
        steps_done=int(raw.get("steps_done", 0)),
        cost_spent_usd=float(raw.get("cost_spent_usd", 0.0)),
        created_at=str(raw.get("created_at", "")),
        updated_at=str(raw.get("updated_at", "")),
        completed_at=raw.get("completed_at"),
        current_phase=raw.get("current_phase") or "interview",
        plan_id=raw.get("plan_id"),
        interview_summary=str(raw.get("interview_summary", "")),
    )


def _seconds_since_iso(iso: str) -> int:
    """Seconds between now (UTC) and `iso` (UTC, written by `_now_iso`).

    `time.mktime` interprets the struct_tm as *local* time, so on any
    non-UTC host it would add the timezone offset and inflate the
    elapsed value (a fresh goal in Moscow could "exhaust" max_wall_time
    immediately). `calendar.timegm` interprets struct_tm as UTC, which
    matches what `_now_iso` writes.
    """
    import calendar

    try:
        t = time.strptime(iso, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return 0
    return max(0, int(time.time() - calendar.timegm(t)))


__all__ = [
    "CheckpointEntry",
    "Goal",
    "GoalBudget",
    "GoalPhase",
    "GoalStatus",
    "append_checkpoint",
    "budget_exhausted",
    "cancel",
    "complete",
    "create_goal",
    "goals_dir",
    "list_goals",
    "pause",
    "read_goal",
    "render_system_block",
    "resume",
    "update_fsm",
]
