"""Parser for `veles module {list,show,add,remove}`."""

from __future__ import annotations

import argparse

from veles.cli._parsers._common import add_project_root_flag


def register(sub: argparse._SubParsersAction) -> None:
    module = sub.add_parser("module", help="Manage project plugins.")
    add_project_root_flag(module)
    module_sub = module.add_subparsers(dest="module_command", required=True)

    module_sub.add_parser("list", help="List installed modules.")

    module_show = module_sub.add_parser("show", help="Print a module's manifest.")
    module_show.add_argument("name")

    module_add = module_sub.add_parser(
        "add", help="Install a module from a git URL or local directory."
    )
    module_add.add_argument("source", help="Git URL (https://, ssh://, git@, *.git) or local path.")
    module_add.add_argument(
        "--name",
        default=None,
        help="Override the install name (default: derived from source).",
    )
    module_add.add_argument(
        "--yes", "-y", action="store_true", help="Skip the confirmation prompt."
    )

    module_remove = module_sub.add_parser("remove", help="Delete an installed module.")
    module_remove.add_argument("name", help="Module name to remove.")
    module_remove.add_argument(
        "--yes", "-y", action="store_true", help="Skip the confirmation prompt."
    )
