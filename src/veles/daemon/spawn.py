"""Detached spawn of `veles daemon start`.

Used by the project wizard (post-recap autostart) and the daemon picker
(`s` / `r` actions). Centralised so the subprocess shape — args, cwd,
io redirection, session detachment — stays consistent.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def spawn_daemon(
    *,
    project_root: str | Path,
    host: str,
    port: int,
    name: str | None = None,
) -> subprocess.Popen[bytes] | None:
    """Spawn `veles daemon start --foreground` detached.

    `--foreground` is critical here: without it the spawned child would
    itself re-enter the detach branch (M113) and fork again forever.
    The child becomes the actual aiohttp server; the parent that called
    `spawn_daemon` returns the Popen handle so the caller can monitor
    the pid file appearing.

    When `name` is set the child re-execs with `--name <name>` so parent
    and child agree on the per-instance pid path and the child resolves
    its own `[daemon.<name>]` provider/model/host/port.

    Returns the Popen handle or None on failure (`OSError` from the
    OS layer — e.g. `python` not on PATH)."""
    cmd = [
        sys.executable,
        "-m",
        "veles",
        "daemon",
        "start",
        "--foreground",
        "--host",
        str(host),
        "--port",
        str(int(port)),
    ]
    if name:
        cmd += ["--name", name]
    try:
        return subprocess.Popen(
            cmd,
            cwd=str(project_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return None


__all__ = ["spawn_daemon"]
