"""`veles tui` — thin CLI shim that boots the Textual-based TUI in
`veles.tui`. The legacy prompt_toolkit + rich REPL that used to live
here was retired by the TUI rewrite milestone (see MILESTONES.md).

Keeping this shim — rather than wiring `veles.cli.__init__` to
`veles.tui.run_tui` directly — preserves the import path
`veles.cli.commands.tui:cmd_tui` that the CLI dispatch and any
out-of-tree tooling rely on. Anything richer than dispatch belongs in
`veles.tui`."""

from __future__ import annotations

import argparse

from veles.core.project import Project
from veles.tui import run_tui


def cmd_tui(args: argparse.Namespace, project: Project) -> int:
    return run_tui(args, project)


__all__ = ["cmd_tui"]
