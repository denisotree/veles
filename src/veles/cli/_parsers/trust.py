"""Parser for `veles trust {list,set,revoke,clear}`."""

from __future__ import annotations

import argparse

from veles.cli._parsers._common import add_project_root_flag


def register(sub: argparse._SubParsersAction) -> None:
    trust = sub.add_parser(
        "trust",
        help="Manage persisted trust grants for sensitive tools.",
    )
    add_project_root_flag(trust)
    trust_sub = trust.add_subparsers(dest="trust_command", required=True)

    trust_sub.add_parser("list", help="Show grants from both user and project scopes.")

    trust_set = trust_sub.add_parser("set", help="Grant a tool without entering the prompt.")
    trust_set.add_argument("tool", help="Tool name (e.g. run_shell, write_file, fetch_url).")
    trust_set.add_argument(
        "--scope",
        choices=("project", "user"),
        default="project",
        help="Where to persist the grant (default: project).",
    )

    trust_revoke = trust_sub.add_parser("revoke", help="Remove a tool grant.")
    trust_revoke.add_argument("tool", help="Tool name to revoke.")
    trust_revoke.add_argument(
        "--scope",
        choices=("project", "user", "both"),
        default="both",
        help="Which scope to revoke from (default: both).",
    )

    trust_clear = trust_sub.add_parser("clear", help="Wipe all grants in a scope.")
    trust_clear.add_argument(
        "--scope",
        choices=("project", "user", "all"),
        default="all",
        help="Which scope to clear (default: all).",
    )
