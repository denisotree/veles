"""Path resolvers for daemon runtime artefacts.

These live under `~/.veles/` (and respect `$VELES_USER_HOME` through
`core/user_paths.py`). They were originally defined inside
`cli/commands/daemon.py`, which created a CLI→TUI dependency: the
daemon picker (TUI) had to import `daemon_log_path` from the CLI
layer to know where to tail the log file. Moving the path helpers
here makes `daemon/` self-sufficient — both CLI and TUI sit above it
as equal-level consumers.
"""

from __future__ import annotations

from pathlib import Path

from veles.core.user_paths import user_home, user_logs_dir


def pid_path() -> Path:
    """`~/.veles/daemon.pid` — single-instance lock."""
    return user_home() / "daemon.pid"


def info_path() -> Path:
    """`~/.veles/daemon.info.json` — sidecar metadata for `daemon status`."""
    return user_home() / "daemon.info.json"


def daemon_log_path(slug: str) -> Path:
    """Per-daemon log file. Slug-keyed so multiple projects don't
    clobber each other; the TUI picker tails this same path when the
    user presses Enter on a row."""
    return user_logs_dir() / f"daemon-{slug}.log"


def instance_pid_path(slug: str, name: str) -> Path:
    """Per-(project, named-session) pid lock (M134/M135).

    The legacy `pid_path()` is a single global lock that allows only one
    daemon per machine. To run several named daemon sessions per project,
    each instance gets its own lock keyed by `(slug, name)`; `name`
    defaults to `default` for the unnamed legacy daemon."""
    return user_home() / f"daemon-{slug}-{name}.pid"


def instance_info_path(slug: str, name: str) -> Path:
    """Per-(project, named-session) info sidecar — companion to
    `instance_pid_path`."""
    return user_home() / f"daemon-{slug}-{name}.info.json"


def instance_log_path(slug: str, name: str) -> Path:
    """Per-(project, named-session) log file (M135)."""
    return user_logs_dir() / f"daemon-{slug}-{name}.log"


__all__ = [
    "daemon_log_path",
    "info_path",
    "instance_info_path",
    "instance_log_path",
    "instance_pid_path",
    "pid_path",
]
