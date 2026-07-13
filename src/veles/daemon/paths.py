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


def pid_path(slug: str) -> Path:
    """`~/.veles/daemon-<slug>.pid` — per-project single-instance lock (M209).

    Slug-keyed like `daemon_log_path`, so daemons for different projects
    no longer lock each other out; two projects sharing a name still
    collide — the same pre-existing limitation as the registry and the
    log files."""
    return user_home() / f"daemon-{slug}.pid"


def info_path(slug: str) -> Path:
    """`~/.veles/daemon-<slug>.info.json` — sidecar metadata for
    `daemon status`, companion to `pid_path`."""
    return user_home() / f"daemon-{slug}.info.json"


def daemon_log_path(slug: str) -> Path:
    """Per-daemon log file. Slug-keyed so multiple projects don't
    clobber each other; the TUI picker tails this same path when the
    user presses Enter on a row."""
    return user_logs_dir() / f"daemon-{slug}.log"


def instance_pid_path(slug: str, name: str) -> Path:
    """Per-(project, named-session) pid lock (M134/M135).

    `pid_path(slug)` locks the project's unnamed daemon; named daemon
    sessions each get their own lock keyed by `(slug, name)` so several
    can run inside one project."""
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
