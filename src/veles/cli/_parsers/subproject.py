"""Parser for `veles subproject {init,list,switch,remove,suggest}`."""

from __future__ import annotations

import argparse

from veles.cli._parsers._common import add_project_root_flag


def register(sub: argparse._SubParsersAction) -> None:
    subproject_cmd = sub.add_parser(
        "subproject",
        help="Manage vertical subprojects (child projects under the active one).",
    )
    add_project_root_flag(subproject_cmd)
    subproject_sub = subproject_cmd.add_subparsers(dest="subproject_command", required=True)

    subproject_init = subproject_sub.add_parser(
        "init",
        help="Initialise a Veles subproject under the active project and register it.",
    )
    subproject_init.add_argument(
        "subdir", help="Relative subdirectory under the active project root."
    )
    subproject_init.add_argument(
        "--name", default=None, help="Override the subproject's name (default: dir name)."
    )
    subproject_init.add_argument(
        "--description",
        default="",
        help="Short description recorded in the parent's subprojects.json.",
    )

    subproject_sub.add_parser("list", help="List subprojects registered under the active project.")

    subproject_switch = subproject_sub.add_parser(
        "switch",
        help="Print the absolute path of a registered subproject (for `cd $(...)`).",
    )
    subproject_switch.add_argument("slug", help="Subproject slug.")

    subproject_remove = subproject_sub.add_parser(
        "remove",
        help="Unregister a subproject (does not delete files).",
    )
    subproject_remove.add_argument("slug", help="Subproject slug.")

    subproject_suggest = subproject_sub.add_parser(
        "suggest",
        help=(
            "Detect thematic clusters in wiki/concepts + wiki/entities and "
            "propose them as candidate subprojects."
        ),
    )
    subproject_suggest.add_argument(
        "--save",
        action="store_true",
        help=(
            "Persist each proposal as wiki/proposals/<slug>.md so the agent's "
            "memory recall surfaces it on future runs."
        ),
    )
    subproject_suggest.add_argument(
        "--min-pages",
        type=int,
        default=4,
        metavar="N",
        help="Minimum pages required to call a connected component a cluster (default: 4).",
    )
    subproject_suggest.add_argument(
        "--min-similarity",
        type=float,
        default=0.25,
        metavar="F",
        help="Minimum title-token Jaccard to connect two pages (default: 0.25).",
    )
