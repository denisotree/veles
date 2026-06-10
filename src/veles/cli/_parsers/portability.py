"""Parser for `veles export {full,template}` and `veles import`."""

from __future__ import annotations

import argparse

from veles.cli._parsers._common import add_project_root_flag


def register(sub: argparse._SubParsersAction) -> None:
    export_cmd = sub.add_parser(
        "export",
        help="Export the active project's state as a tar.gz bundle.",
    )
    add_project_root_flag(export_cmd)
    export_sub = export_cmd.add_subparsers(dest="export_command", required=True)

    export_full = export_sub.add_parser(
        "full",
        help=(
            "Pack the entire project (.veles + AGENTS.md). For backup/migrate. "
            "Excludes runtime ephemera (*.lock, budget.state.json)."
        ),
    )
    export_full.add_argument("path", help="Output bundle path (.tar.gz).")

    export_template = export_sub.add_parser(
        "template",
        help=(
            "Pack a sanitised subset for sharing: schema + skills + modules + "
            "non-session wiki pages. Strips memory.db, sources/, sessions/, "
            "trust.json, and runs PII regex over included text files."
        ),
    )
    export_template.add_argument("path", help="Output bundle path (.tar.gz).")

    import_cmd = sub.add_parser(
        "import",
        help="Import a Veles bundle into a project directory.",
    )
    import_cmd.add_argument("path", help="Bundle path (.tar.gz) created by `veles export`.")
    import_cmd.add_argument(
        "--into",
        default=None,
        help="Target directory (default: current working directory).",
    )
    import_cmd.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing .veles/ at the target.",
    )
