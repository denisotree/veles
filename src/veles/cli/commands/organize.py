"""`veles organize` — thin CLI shim (M175).

All logic lives in the built-in `veles.modules.organize` module; this file
only adapts the parsed args to the module entry point, exactly as
`cli/commands/add.py` delegates into `modules/wiki`.
"""

from __future__ import annotations

import argparse

from veles.core.project import Project


def cmd_organize(args: argparse.Namespace, project: Project) -> int:
    from veles.modules.organize import run

    return run(args, project)
