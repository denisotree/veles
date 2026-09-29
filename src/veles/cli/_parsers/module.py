"""Parser for `veles module {list,show,add,remove,approve}`."""

from __future__ import annotations

import argparse

from veles.cli._parsers._common import add_project_root_flag


def register(sub: argparse._SubParsersAction) -> None:
    module = sub.add_parser("module", help="Manage project plugins.")
    add_project_root_flag(module)
    module_sub = module.add_subparsers(dest="module_command", required=True)

    user_help = "User-level modules (~/.veles/modules), loaded in every project."

    module_list = module_sub.add_parser("list", help="List installed modules.")
    module_list.add_argument("--user", action="store_true", help=user_help)

    module_show = module_sub.add_parser("show", help="Print a module's manifest.")
    module_show.add_argument("name", help="Module name.")
    module_show.add_argument("--user", action="store_true", help=user_help)

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
    module_add.add_argument("--user", action="store_true", help=user_help)

    module_remove = module_sub.add_parser("remove", help="Delete an installed module.")
    module_remove.add_argument("name", help="Module name to remove.")
    module_remove.add_argument(
        "--yes", "-y", action="store_true", help="Skip the confirmation prompt."
    )
    module_remove.add_argument("--user", action="store_true", help=user_help)

    module_approve = module_sub.add_parser(
        "approve", help="Approve an installed module's current code so it loads."
    )
    module_approve.add_argument("name", help="Module name.")
    module_approve.add_argument("--user", action="store_true", help=user_help)
