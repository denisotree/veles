"""Parser for `veles tool {list,show,promote}`.

M120.5: VISION §5.4 "promote project↔user" verb plus a `list` /
`show` pair that lets the user inspect what's catalogued. Builtin
tools register at import time via the `@tool` decorator and don't
participate in this CLI surface — they live in `src/veles/core/tools/
builtin/*.py`, not in any user-writable directory.

Conscious omissions deferred to M120b:
- `veles tool add` (manual install via the `tool_installer` skill);
- `veles tool remove` (we don't yet have an undo story for tools the
  agent created — separate skills-level deletion semantics needed).
"""

from __future__ import annotations

import argparse

from veles.cli._parsers._common import add_project_root_flag


def register(sub: argparse._SubParsersAction) -> None:
    tool = sub.add_parser("tool", help="Manage agent-generated and user tools.")
    add_project_root_flag(tool)
    tool_sub = tool.add_subparsers(dest="tool_command", required=True)

    tool_sub.add_parser(
        "list", help="List tools catalogued in this project's memory.db."
    )

    tool_show = tool_sub.add_parser(
        "show", help="Print one tool's manifest + telemetry."
    )
    tool_show.add_argument("name", help="Tool name (as registered).")

    tool_promote = tool_sub.add_parser(
        "promote",
        help="Move a project-level tool .py to `~/.veles/tools/` so every project sees it.",
    )
    tool_promote.add_argument("name", help="Tool name (as registered).")
    tool_promote.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip the confirmation prompt.",
    )
