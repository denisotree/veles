"""`veles init` — bootstrap a Veles project in cwd."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from veles.core.project import ProjectAlreadyExists, init_project


def cmd_init(args: argparse.Namespace) -> int:
    from veles.cli import _register_project

    cwd = Path.cwd()
    try:
        project = init_project(
            cwd,
            name=args.name,
            force=args.force,
            layout=getattr(args, "layout", None) or "llm-wiki",
        )
    except ProjectAlreadyExists as exc:
        print(f"error: {exc}", file=sys.stderr)
        print("       use `veles init --force` to reset.", file=sys.stderr)
        return 1
    _register_project(project)
    print(f"initialized Veles project '{project.name}' at {project.root}")
    print(f"  state: {project.state_dir}")
    print(f"  agents: {project.agents_md_path}")
    print('edit AGENTS.md to add project context, then run `veles run "..."`.')
    return 0
