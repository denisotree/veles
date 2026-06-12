"""Parser for `veles route {show,set,reset,refresh}`."""

from __future__ import annotations

import argparse

from veles.cli._parsers._common import add_project_root_flag


def register(sub: argparse._SubParsersAction) -> None:
    route_cmd = sub.add_parser(
        "route",
        help="Inspect / edit the per-task ensemble routing (which provider+model per task type).",
    )
    add_project_root_flag(route_cmd)
    route_sub = route_cmd.add_subparsers(dest="route_command", required=True)

    route_sub.add_parser("show", help="Print the resolved routing table for the active project.")

    route_set = route_sub.add_parser(
        "set",
        help='Set a task → spec mapping. Spec is "<provider>:<model>".',
    )
    route_set.add_argument(
        "task",
        help=(
            "Task type: default, curator, compressor, insights, skills, advisor, vision, embedding."
        ),
    )
    route_set.add_argument(
        "spec",
        help='Spec, e.g. "anthropic:claude-haiku-4.5" or "openrouter:openai/gpt-4o-mini".',
    )

    route_reset = route_sub.add_parser(
        "reset", help="Reset one task (or all if none given) back to the default routing."
    )
    route_reset.add_argument(
        "task", nargs="?", default=None, help="Task type to reset; omit to reset all tasks."
    )

    route_refresh = route_sub.add_parser(
        "refresh",
        help=(
            "Re-parse natural-language routing hints from AGENTS.md into "
            "routing.nl.toml. Explicit [routing.tasks] entries in config.toml always win."
        ),
    )
    route_refresh.add_argument(
        "--force",
        action="store_true",
        help="Re-run even when AGENTS.md hasn't changed since the last refresh.",
    )
