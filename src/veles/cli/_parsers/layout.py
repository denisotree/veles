"""Parser for `veles layout {sync}`."""

from __future__ import annotations

import argparse

from veles.cli._parsers._common import add_project_root_flag


def register(sub: argparse._SubParsersAction) -> None:
    layout_cmd = sub.add_parser("layout", help="Layout-pack maintenance.")
    add_project_root_flag(layout_cmd)
    layout_sub = layout_cmd.add_subparsers(dest="layout_command", required=True)
    layout_sub.add_parser(
        "sync",
        help=(
            "Re-apply the active layout pack's scaffold to this project — create "
            "any new category / structure dirs (e.g. after the pack added "
            "diary/tasks/projects) without re-initialising. Idempotent."
        ),
    )
