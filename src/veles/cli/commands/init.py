"""`veles init` — bootstrap a Veles project in cwd."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from veles.core.project import LAYOUT_DEFAULT, ProjectAlreadyExists, init_project


def cmd_init(args: argparse.Namespace) -> int:
    from veles.cli._project import _register_project

    layout = getattr(args, "layout", None) or (_ask_layout() if _is_tty() else LAYOUT_DEFAULT)
    if not _layout_available(layout):
        print(
            f"error: layout {layout!r} is not installed — nothing was created.",
            file=sys.stderr,
        )
        return 1
    cwd = Path.cwd()
    try:
        project = init_project(cwd, name=args.name, force=args.force, layout=layout)
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


def _ask_layout() -> str:
    from veles.cli.wizard import _ask_choice
    from veles.core.registry.ensure import available_layouts

    choices = tuple(available_layouts())
    return _ask_choice(_prompter, "Layout", choices, default=LAYOUT_DEFAULT)


def _layout_available(name: str) -> bool:
    """Installed, or installed now (offered at a terminal, with its dependencies)."""
    from veles.core.layout.discovery import find_layout
    from veles.core.registry import ensure

    if find_layout(name, None) is not None:
        return True
    return ensure.ensure_extension(ensure.LayoutNeed(name), None, interactive=_is_tty())


def _is_tty() -> bool:
    return sys.stdin.isatty()


def _prompter(prompt: str, default: str | None) -> str:
    from veles.cli.wizard import _default_prompter

    return _default_prompter(prompt, default)
