"""Per-process directories for a CLI delegate (release E).

A delegated CLI (claude, agy) reads its MCP config, and the Veles MCP server it
spawns reads the token budget, from files. One shared `.veles/mcp.json` let two
processes in one project rewrite each other's config mid-run. Now each process
gets `<project>/.veles/tmp/delegate-<pid>/`, and a delegate that needs a working
directory of its own gets one outside every project (`delegate_workspace`). Both
are removed when the process exits and swept when a crashed process left one.
"""

from __future__ import annotations

import atexit
import hashlib
import os
import shutil
from pathlib import Path

from veles.core.process import is_alive
from veles.core.project import Project
from veles.core.user_paths import user_home

# The agent's file tools refuse anything under `.veles/tmp/delegate-*`
# (`core/layout/writable.py`): claude runs what its --mcp-config names.
DIR_PREFIX = "delegate-"
_registered: set[Path] = set()


def delegate_dir(project: Project) -> Path:
    return _claim(project.tmp_dir / f"{DIR_PREFIX}{os.getpid()}", f"{DIR_PREFIX}*")


def delegate_budget_file(project: Project) -> Path:
    return delegate_dir(project) / "budget.json"


def delegate_workspace(project: Project, name: str) -> Path:
    """A working directory for delegate `name`, outside every project:
    `<user home>/tmp/<name>/<project key>-<pid>/`. A CLI that reads config from its
    working directory and the folders above it (agy reads every `.agents/` up to the
    repository root) then never picks up the project's own — a cloned repo's hooks
    or MCP servers. Keyed by project, so one process serving several projects keeps
    their configs apart."""
    key = hashlib.sha256(str(project.root.resolve()).encode()).hexdigest()[:12]
    return _claim(user_home() / "tmp" / name / f"{key}-{os.getpid()}", "*-*")


def _claim(path: Path, siblings: str) -> Path:
    if path not in _registered:
        _sweep(path.parent, siblings)
        path.mkdir(parents=True, exist_ok=True)
        atexit.register(shutil.rmtree, path, ignore_errors=True)
        _registered.add(path)
    return path


def _sweep(parent: Path, pattern: str) -> None:
    """Remove the `<…>-<pid>` directories of processes that are gone."""
    for stale in parent.glob(pattern):
        pid = stale.name.rpartition("-")[2]
        if pid.isdigit() and not is_alive(int(pid)):
            shutil.rmtree(stale, ignore_errors=True)
