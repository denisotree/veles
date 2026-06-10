"""Parser for `veles goal {list,show,start,checkpoint,pause,resume,done,cancel}`."""

from __future__ import annotations

import argparse


def register(sub: argparse._SubParsersAction) -> None:
    goal = sub.add_parser(
        "goal",
        help="Manage long-horizon objectives with budgets and checkpoints.",
    )
    goal_sub = goal.add_subparsers(dest="goal_command", required=True)

    g_list = goal_sub.add_parser("list", help="List goals (optionally filter by status).")
    g_list.add_argument(
        "--status",
        choices=("active", "paused", "completed", "blocked", "cancelled"),
        default=None,
    )

    g_show = goal_sub.add_parser("show", help="Show a single goal in detail.")
    g_show.add_argument("id")
    g_show.add_argument("--json", action="store_true")

    g_start = goal_sub.add_parser("start", help="Create a new goal in active status.")
    g_start.add_argument("objective", help="One-line objective sentence.")
    g_start.add_argument("--scope", default=None)
    g_start.add_argument(
        "--done-when",
        dest="done_when",
        default=None,
        help="Done-condition (e.g. 'report.md exists and cites ≥3 sources').",
    )
    g_start.add_argument("--max-steps", type=int, default=30)
    g_start.add_argument("--max-cost-usd", type=float, default=5.0)
    g_start.add_argument("--max-wall-time-s", type=int, default=3600)
    g_start.add_argument("--forbid", action="append", default=None, metavar="ACTION")
    g_start.add_argument("--approve", action="append", default=None, metavar="ACTION")

    g_cp = goal_sub.add_parser("checkpoint", help="Append a progress entry to a goal.")
    g_cp.add_argument("id")
    g_cp.add_argument("note", help="What progressed.")
    g_cp.add_argument("--evidence", default=None, help="Optional artifact URI / ref.")
    g_cp.add_argument("--cost-usd", type=float, default=None)
    g_cp.add_argument(
        "--no-advance",
        action="store_true",
        help="Don't count this checkpoint against max_steps (info-only note).",
    )

    g_pause = goal_sub.add_parser("pause", help="Pause an active goal.")
    g_pause.add_argument("id")

    g_resume = goal_sub.add_parser("resume", help="Resume a paused goal.")
    g_resume.add_argument("id")

    g_done = goal_sub.add_parser("done", help="Mark a goal completed.")
    g_done.add_argument("id")
    g_done.add_argument("--evidence", default=None, help="Optional final-evidence note.")

    g_cancel = goal_sub.add_parser("cancel", help="Cancel a non-completed goal.")
    g_cancel.add_argument("id")
    g_cancel.add_argument("--reason", default=None)
