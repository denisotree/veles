"""A per-process directory for a CLI delegate's run files (release E).

A delegated CLI (claude, agy) reads its MCP config, and the Veles MCP server it
spawns reads the token budget, from files. One shared `.veles/mcp.json` let two
processes in one project rewrite each other's config mid-run. Now each process
gets `<project>/.veles/tmp/delegate-<pid>/`: removed when the process exits,
swept when a crashed process left one behind.
"""

from __future__ import annotations

import atexit
import os
import shutil
from pathlib import Path

from veles.core.process import is_alive
from veles.core.project import Project

_PREFIX = "delegate-"
_registered: set[Path] = set()


def delegate_dir(project: Project) -> Path:
    path = project.tmp_dir / f"{_PREFIX}{os.getpid()}"
    if path not in _registered:
        _sweep(path.parent)
        path.mkdir(parents=True, exist_ok=True)
        atexit.register(shutil.rmtree, path, ignore_errors=True)
        _registered.add(path)
    return path


def delegate_budget_file(project: Project) -> Path:
    return delegate_dir(project) / "budget.json"


def _sweep(parent: Path) -> None:
    for stale in parent.glob(f"{_PREFIX}*"):
        pid = stale.name[len(_PREFIX) :]
        if pid.isdigit() and not is_alive(int(pid)):
            shutil.rmtree(stale, ignore_errors=True)
