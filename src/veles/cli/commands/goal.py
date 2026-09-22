"""`veles goal {list,show,start,pause,resume,cancel}`.

M276: `start` and `resume` *run* the goal. Before, `start` wrote
`goals/<id>.json`, printed "started goal …" and returned — and no runtime ever
read that id (GoalMode creates its own goal when it has none), so nothing
started. Its `--forbid` / `--approve` flags ("pre-approve an action so it runs
without a prompt") were read by nothing anywhere; they are gone rather than
kept as a promise of protection that does not exist. `checkpoint` and `done`
hand-edited a goal's progress and status, which a running driver now owns.
"""

from __future__ import annotations

import argparse
import json
import sys

from veles.core.goal import (
    GoalBudget,
    budget_exhausted,
    cancel,
    list_goals,
    pause,
    read_goal,
    resume,
)
from veles.core.project import Project

# Exit codes for scripting — the reason M123 kept a CLI wrapper around goal mode.
_EXIT_COMPLETED = 0
_EXIT_CANCELLED = 3  # budget, infeasible, or cancelled
_EXIT_STOPPED = 4  # stalled, turn cap, paused, or needs a person


def cmd_goal(args: argparse.Namespace, project: Project) -> int:
    verb = args.goal_command
    state = project.state_dir
    if verb == "list":
        return _list(state, args)
    if verb == "show":
        return _show(state, args)
    if verb == "start":
        return _start(args, project)
    if verb == "pause":
        return _pause(state, args)
    if verb == "resume":
        return _resume(args, project)
    if verb == "cancel":
        return _cancel(state, args)
    print(f"unknown goal verb: {verb!r}", file=sys.stderr)
    return 2


def _list(state, args):
    goals = list_goals(state, status=args.status)
    if not goals:
        print("(no goals)", file=sys.stderr)
        return 0
    for g in goals:
        flag = budget_exhausted(g)
        head = f"{g.id}  [{g.status:9}]  {g.objective}"
        if flag:
            head += f"  ⚠ {flag}"
        print(head)
        print(
            f"      steps {g.steps_done}/{g.budget.max_steps}  "
            f"${g.cost_spent_usd:.2f}/${g.budget.max_cost_usd:.2f}  "
            f"phase {g.current_phase}  created {g.created_at}"
        )
    return 0


def _show(state, args):
    g = read_goal(state, args.id)
    if g is None:
        print(f"no goal with id {args.id!r}", file=sys.stderr)
        return 1
    if args.json:
        from dataclasses import asdict

        print(json.dumps(asdict(g), ensure_ascii=False, indent=2))
        return 0
    print(f"Goal {g.id}  [{g.status}]  phase {g.current_phase}")
    print(f"  Objective:     {g.objective}")
    if g.scope:
        print(f"  Scope:         {g.scope}")
    if g.done_condition:
        print(f"  Done when:     {g.done_condition}")
    print(
        f"  Budget:        {g.steps_done}/{g.budget.max_steps} steps, "
        f"${g.cost_spent_usd:.2f}/${g.budget.max_cost_usd:.2f}, "
        f"{g.budget.max_wall_time_s}s wall"
    )
    print(f"  Created:       {g.created_at}")
    if g.completed_at:
        print(f"  Completed:     {g.completed_at}")
    if g.progress:
        print("  Progress:")
        for p in g.progress:
            line = f"    {p.ts}  {p.description}"
            if p.evidence_ref:
                line += f"  ({p.evidence_ref})"
            print(line)
    return 0


def _start(args, project: Project) -> int:
    from veles.core.modes.goal_driver import start_goal

    budget = GoalBudget(
        max_steps=args.max_steps,
        max_cost_usd=args.max_cost_usd,
        max_wall_time_s=args.max_wall_time_s,
    )
    try:
        g = start_goal(
            project.state_dir,
            objective=args.objective,
            done_condition=args.done_when or "",
            scope=args.scope or "",
            budget=budget,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"goal {g.id}: {g.objective}", file=sys.stderr)
    return _drive(args, project, g.id)


def _pause(state, args):
    try:
        pause(state, args.id)
    except (KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"paused goal {args.id}", file=sys.stderr)
    return 0


def _resume(args, project: Project) -> int:
    """Continue a paused goal — or an active one whose run stopped (stalled,
    turn cap, Ctrl+C): those stay `active`, and the stop message itself points
    here, so only `paused` needs the status transition."""
    goal = read_goal(project.state_dir, args.id)
    try:
        if goal is None or goal.status != "active":
            resume(project.state_dir, args.id)
    except (KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return _drive(args, project, args.id)


def _cancel(state, args):
    try:
        cancel(state, args.id, reason=args.reason or "")
    except (KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"goal {args.id} cancelled", file=sys.stderr)
    return 0


def _drive(args, project: Project, goal_id: str) -> int:
    """Run the goal unless another process already is. A goal left `active`
    by a stall looks exactly like one running in another terminal, and the
    stop message says to `resume` — a second driver would run the same step
    twice, spend twice, and race on `goals/<id>.json`."""
    from veles.core.file_lock import LockHeld, file_lock
    from veles.core.goal import goals_dir

    try:
        with file_lock(goals_dir(project.state_dir) / f"{goal_id}.lock", blocking=False):
            return _drive_locked(args, project, goal_id)
    except LockHeld:
        print(f"error: goal {goal_id} is already running in another process", file=sys.stderr)
        return 2


def _drive_locked(args, project: Project, goal_id: str) -> int:
    """Run the goal in the foreground on the same runtime the REPL builds —
    provider, model, tools, compressor, session store — so a goal behaves the
    same here as it does after `/goal` in the REPL."""
    from veles.cli.repl.runtime import _build_runtime
    from veles.core.agent_events import SystemLine
    from veles.core.modes import ModeContext
    from veles.core.modes.goal_driver import drive_goal

    runtime = _build_runtime(args, project)
    if runtime is None:
        return 2
    state, factory, store, _subagent_factory = runtime

    def post(event) -> None:
        # Phase transitions go to stderr so stdout stays the agent's own text.
        if isinstance(event, SystemLine):
            print(f"  {event.text}", file=sys.stderr, flush=True)

    def on_text(delta: str) -> None:
        sys.stdout.write(delta)
        sys.stdout.flush()

    ctx = ModeContext(
        state=state,
        project=project,
        factory=factory,
        post=post,
        on_text=on_text,
        on_event=lambda _event: None,
    )
    try:
        outcome = drive_goal(ctx, goal_id)
    except KeyboardInterrupt:
        print(
            f"\ninterrupted — `veles goal resume {goal_id}` continues from here",
            file=sys.stderr,
        )
        return _EXIT_STOPPED
    finally:
        store.close()

    print(f"\ngoal {goal_id}: {outcome.status} — {outcome.reason}", file=sys.stderr)
    if outcome.completed:
        return _EXIT_COMPLETED
    if outcome.status == "cancelled":
        return _EXIT_CANCELLED
    if outcome.status in ("stalled", "turn_cap", "paused"):
        print(f"`veles goal resume {goal_id}` continues from here", file=sys.stderr)
    return _EXIT_STOPPED
