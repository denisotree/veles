"""Parser for `veles project {list,add,remove,switch}`."""

from __future__ import annotations

import argparse


def register(sub: argparse._SubParsersAction) -> None:
    project_cmd = sub.add_parser("project", help="Manage the multi-project registry.")
    project_sub = project_cmd.add_subparsers(dest="project_command", required=True)

    project_sub.add_parser("list", help="List registered projects, most-recent first.")

    project_add = project_sub.add_parser(
        "add", help="Register an existing Veles project directory."
    )
    project_add.add_argument("path", help="Absolute or relative path to the project root.")
    project_add.add_argument(
        "--slug",
        default=None,
        help="Override the registered slug (default: derived from project name).",
    )

    project_remove = project_sub.add_parser(
        "remove", help="Remove a project from the registry (does not delete files)."
    )
    project_remove.add_argument("slug", help="Project slug to unregister.")

    project_switch = project_sub.add_parser(
        "switch",
        help="Print the absolute path of a registered project; bumps last-active.",
    )
    project_switch.add_argument("slug", help="Project slug to resolve to a path.")
