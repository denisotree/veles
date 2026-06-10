"""Advisory exclusive file lock for read-modify-write of shared files.

Used by `bump_telemetry` (M30) so concurrent skill invocations from the
parent process and one or more MCP child processes don't lose updates
on SKILL.md frontmatter counters. The lock file is a sidecar (e.g.
`<skill.path>.lock`); flock(2) is per open-file-description, so opening
the same path from different processes — or different threads in one
process — yields independent fds that serialize on `LOCK_EX`.

`budget_state.save_atomic` does *not* need this lock by design: it
writes a complete snapshot built from the in-process `TokenBudget`
(no read-modify-write), and parent vs. MCP-child writes are sequenced
by the delegate-runs-while-parent-blocks protocol. If that invariant
is ever broken, wrap that call site too.

POSIX-only; on Windows the manager is a noop and emits one warning at
import time. Veles itself targets Linux/macOS/WSL2 per PLAN.md §13 #9.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

if sys.platform != "win32":
    import fcntl
else:  # pragma: no cover - non-target platform
    fcntl = None  # type: ignore[assignment]


@contextmanager
def file_lock(lock_path: Path) -> Iterator[None]:
    """Hold an exclusive flock on `lock_path` for the body's duration.

    The lock file is created if missing. On exit the lock is released
    (also released implicitly if an exception propagates). The file
    itself is left in place — flock state lives on the open fd, not on
    disk, so cleanup adds no value.
    """
    if fcntl is None:  # pragma: no cover - non-target platform
        yield
        return
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w", encoding="utf-8") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
