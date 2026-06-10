"""Parser for `veles schema {validate,edit,fix}`."""

from __future__ import annotations

import argparse

from veles.cli._parsers._common import add_project_root_flag


def register(sub: argparse._SubParsersAction) -> None:
    schema_cmd = sub.add_parser("schema", help="Validate / edit AGENTS.md.")
    add_project_root_flag(schema_cmd)
    schema_sub = schema_cmd.add_subparsers(dest="schema_command", required=True)
    schema_sub.add_parser("validate", help="Check AGENTS.md for required H2 sections.")
    schema_sub.add_parser(
        "edit",
        help="Open AGENTS.md in $EDITOR (default: vi); validate after exit.",
    )
    schema_sub.add_parser(
        "fix",
        help="Interactively add missing AGENTS.md sections via LLM wizard.",
    )
