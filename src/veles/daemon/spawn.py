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
    log_path: str | Path | None = None,
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

    `log_path` (when given) receives the child's stdout+stderr, appended —
    a detached child that crashes before (or outside) its logging setup
    used to die into /dev/null with zero trace (live 2026-07-09: a bind
    failure right after startup left no evidence anywhere). Callers should
    pass the daemon's own log file so everything lands in one place.

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
    log_file = None
    if log_path is not None:
        try:
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            log_file = open(log_path, "ab")  # noqa: SIM115 — fd is handed to the child
        except OSError:
            log_file = None
    try:
        return subprocess.Popen(
            cmd,
            cwd=str(project_root),
            stdout=log_file if log_file is not None else subprocess.DEVNULL,
            stderr=subprocess.STDOUT if log_file is not None else subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return None
    finally:
        # The child holds its own duplicate of the fd; close the parent's copy.
        if log_file is not None:
            log_file.close()


__all__ = ["spawn_daemon"]
