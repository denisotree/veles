"""Parser for `veles goal {list,show,start,pause,resume,cancel}`."""

from __future__ import annotations

import argparse

from veles.cli._parsers._common import add_common_run_flags


def register(sub: argparse._SubParsersAction) -> None:
    goal = sub.add_parser(
        "goal",
        help="Run long-horizon goals to a done condition, within a budget.",
    )
    goal_sub = goal.add_subparsers(dest="goal_command", required=True)

    g_list = goal_sub.add_parser("list", help="List goals (optionally filter by status).")
    g_list.add_argument(
        "--status",
        choices=("active", "paused", "completed", "blocked", "cancelled"),
        default=None,
        help="Only show goals in this status.",
    )

    g_show = goal_sub.add_parser("show", help="Show a single goal in detail.")
    g_show.add_argument("id", help="Goal id.")
    g_show.add_argument("--json", action="store_true", help="Output the goal as JSON.")

    g_start = goal_sub.add_parser(
        "start",
        help="Run a goal now: plan, execute and check until it is done or the budget ends.",
        description=(
            "Runs in the foreground. Tool approvals prompt in this terminal as they "
            "do for `veles run`; without a terminal (cron) write actions are refused "
            "unless autopilot is on (`veles autopilot enable --until …`)."
        ),
    )
    g_start.add_argument("objective", help="One-line objective sentence.")
    g_start.add_argument(
        "--done-when",
        dest="done_when",
        required=True,
        help="Done condition the advisor checks, e.g. 'report.md exists and cites ≥3 sources'.",
    )
    g_start.add_argument("--scope", default=None, help="Optional scope / context for the goal.")
    # M283: no hardcoded defaults here — an omitted flag takes `[goal]` from the
    # project's config.toml, else the built-in 30 steps / $5 / 3600 s.
    g_start.add_argument(
        "--max-steps",
        type=int,
        default=None,
        help="Step budget before the goal stops (default: [goal] max_steps, else 30).",
    )
    g_start.add_argument(
        "--max-cost-usd",
        type=float,
        default=None,
        help="Cost budget in USD (default: [goal] max_cost_usd, else 5.0).",
    )
    g_start.add_argument(
        "--max-wall-time-s",
        type=int,
        default=None,
        help="Wall-clock budget in seconds (default: [goal] max_wall_time_s, else 3600).",
    )
    add_common_run_flags(g_start)

    g_pause = goal_sub.add_parser(
        "pause", help="Pause a goal; a running `start`/`resume` stops at its next turn."
    )
    g_pause.add_argument("id", help="Goal id.")

    g_resume = goal_sub.add_parser(
        "resume", help="Continue a paused or interrupted goal from where it stopped."
    )
    g_resume.add_argument("id", help="Goal id.")
    add_common_run_flags(g_resume)

    g_cancel = goal_sub.add_parser("cancel", help="Cancel a non-completed goal.")
    g_cancel.add_argument("id", help="Goal id.")
    g_cancel.add_argument("--reason", default=None, help="Optional cancellation reason.")
