"""`veles goal {list,show,start,checkpoint,pause,resume,done,cancel}` (M-deferred opened)."""

from __future__ import annotations

import argparse
import json
import sys

from veles.core.goal import (
    GoalBudget,
    append_checkpoint,
    budget_exhausted,
    cancel,
    complete,
    create_goal,
    list_goals,
    pause,
    read_goal,
    resume,
)
from veles.core.project import Project


def cmd_goal(args: argparse.Namespace, project: Project) -> int:
    verb = args.goal_command
    state = project.state_dir
    if verb == "list":
        return _list(state, args)
    if verb == "show":
        return _show(state, args)
    if verb == "start":
        return _start(state, args)
    if verb == "checkpoint":
        return _checkpoint(state, args)
    if verb == "pause":
        return _pause(state, args)
    if verb == "resume":
        return _resume(state, args)
    if verb == "done":
        return _done(state, args)
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
            f"created {g.created_at}"
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
    print(f"Goal {g.id}  [{g.status}]")
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
    if g.forbidden_actions:
        print(f"  Forbidden:     {', '.join(g.forbidden_actions)}")
    if g.approval_required_for:
        print(f"  Approval for:  {', '.join(g.approval_required_for)}")
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


def _start(state, args):
    budget = GoalBudget(
        max_steps=args.max_steps,
        max_cost_usd=args.max_cost_usd,
        max_wall_time_s=args.max_wall_time_s,
    )
    try:
        g = create_goal(
            state,
            objective=args.objective,
            scope=args.scope or "",
            done_condition=args.done_when or "",
            budget=budget,
            forbidden_actions=args.forbid or [],
            approval_required_for=args.approve or [],
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"started goal {g.id}: {g.objective}", file=sys.stderr)
    return 0


def _checkpoint(state, args):
    try:
        append_checkpoint(
            state,
            args.id,
            description=args.note,
            evidence_ref=args.evidence,
            cost_usd=args.cost_usd or 0.0,
            advance_step=not args.no_advance,
        )
    except (KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"checkpoint recorded for {args.id}", file=sys.stderr)
    return 0


def _pause(state, args):
    try:
        pause(state, args.id)
    except (KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"paused goal {args.id}", file=sys.stderr)
    return 0


def _resume(state, args):
    try:
        resume(state, args.id)
    except (KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"resumed goal {args.id}", file=sys.stderr)
    return 0


def _done(state, args):
    try:
        complete(state, args.id, evidence=args.evidence)
    except (KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"goal {args.id} marked completed", file=sys.stderr)
    return 0


def _cancel(state, args):
    try:
        cancel(state, args.id, reason=args.reason or "")
    except (KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"goal {args.id} cancelled", file=sys.stderr)
    return 0
