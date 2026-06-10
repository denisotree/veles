"""Parser for `veles sessions {list,show,delete,search}`."""

from __future__ import annotations

import argparse

from veles.cli._parsers._common import add_project_root_flag


def register(sub: argparse._SubParsersAction) -> None:
    sessions = sub.add_parser("sessions", help="Inspect/manage saved sessions.")
    add_project_root_flag(sessions)
    sessions_sub = sessions.add_subparsers(dest="sessions_command", required=True)

    sessions_list = sessions_sub.add_parser("list", help="List recent sessions.")
    sessions_list.add_argument(
        "--limit", type=int, default=20, help="Max sessions to show (default: 20)."
    )

    sessions_show = sessions_sub.add_parser("show", help="Print a session's history.")
    sessions_show.add_argument("session_id")

    sessions_delete = sessions_sub.add_parser("delete", help="Delete a session and all its turns.")
    sessions_delete.add_argument("session_id")

    sessions_search = sessions_sub.add_parser(
        "search",
        help="FTS5 search over turn content across all sessions.",
    )
    sessions_search.add_argument("query", help="FTS5 query (tokens are AND'd).")
    sessions_search.add_argument(
        "--limit", type=int, default=10, help="Max hits to print (default: 10)."
    )
    sessions_search.add_argument(
        "--role",
        choices=("user", "assistant", "both", "all"),
        default="both",
        help="Which message roles to include (default: both = user+assistant).",
    )
    sessions_search.add_argument(
        "--since",
        default=None,
        metavar="DUR",
        help="Only turns newer than this duration (e.g. 7d, 12h).",
    )
