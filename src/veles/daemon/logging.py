"""File-backed logging setup for the daemon process.

`setup_daemon_logging(slug, ...)` wires a RotatingFileHandler into the
`veles.daemon`, `veles.channels`, `veles.cli.commands.daemon`, and
`veles.core.agent` loggers so per-run lifecycle events, tool calls,
file ops, Telegram inbound updates, and unexpected errors land in
`~/.veles/logs/daemon-<slug>.log`. The handler is named
(`veles-daemon-<slug>`) so repeated calls (tests, hot-reloads) don't
pile up duplicate handlers.

Level, rotation size, and backup count are configurable via the
`[daemon.logging]` section in `<project>/.veles/project.toml`. Env
`VELES_LOG_LEVEL` overrides everything for one-off debugging.

`truncate_for_log(text, cap)` is the project-wide helper for clipping
long tool args/results so the log file doesn't balloon when an agent
reads a 10MB file.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from veles.daemon.paths import daemon_log_path

_LOGGER_NAMES = (
    "veles.daemon",
    "veles.channels",
    "veles.cli.commands.daemon",
    "veles.core.agent",
    "veles.core.tools",
)

DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10 MiB
DEFAULT_BACKUP_COUNT = 5
DEFAULT_TRUNCATE_CHARS = 2000
DEFAULT_LEVEL = "INFO"


def setup_daemon_logging(
    slug: str,
    *,
    level: str = DEFAULT_LEVEL,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
) -> Path:
    """Configure file logging for the daemon process; return the log
    file path so the caller can surface it on startup.

    `VELES_LOG_LEVEL` env overrides `level`. Idempotent — calling twice
    with the same slug leaves the handler set untouched."""
    log_path = daemon_log_path(slug)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    handler.set_name(f"veles-daemon-{slug}")

    env_level = os.environ.get("VELES_LOG_LEVEL")
    resolved_level_str = (env_level or level or DEFAULT_LEVEL).upper()
    resolved_level = getattr(logging, resolved_level_str, logging.INFO)

    for logger_name in _LOGGER_NAMES:
        log = logging.getLogger(logger_name)
        already = [h for h in log.handlers if h.get_name() == handler.get_name()]
        if not already:
            log.addHandler(handler)
        log.setLevel(resolved_level)
    return log_path


def truncate_for_log(text: object, cap: int = DEFAULT_TRUNCATE_CHARS) -> str:
    """Convert `text` to str and elide if over `cap`. The suffix records
    the original byte count so a reader can spot when an interesting
    payload was trimmed."""
    s = str(text) if text is not None else ""
    if cap <= 0 or len(s) <= cap:
        return s
    return f"{s[:cap]}… (truncated, {len(s)} chars total)"


__all__ = ["DEFAULT_TRUNCATE_CHARS", "setup_daemon_logging", "truncate_for_log"]
