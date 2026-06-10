"""Parser for `veles self-doc {refresh,show}`."""

from __future__ import annotations

import argparse

from veles.cli._parsers._common import add_project_root_flag


def register(sub: argparse._SubParsersAction) -> None:
    self_doc_cmd = sub.add_parser(
        "self-doc", help="Generate and display project self-documentation."
    )
    add_project_root_flag(self_doc_cmd)
    self_doc_sub = self_doc_cmd.add_subparsers(dest="self_doc_cmd")
    self_doc_sub.add_parser("refresh", help="Generate and write wiki/self-doc/overview.md.")
    self_doc_sub.add_parser("show", help="Print the current self-documentation page.")
