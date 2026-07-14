"""File-backed logging setup for the daemon process.

`setup_daemon_logging(slug, ...)` wires a RotatingFileHandler into the
`veles.daemon`, `veles.channels`, `veles.cli.commands.daemon`, and
`veles.core` loggers so per-run lifecycle events, tool calls, file ops,
Telegram inbound updates, background-runner failures, and unexpected
errors land in `~/.veles/logs/daemon-<slug>.log`. `veles.core` is wired
as a whole (M210): it used to be just `veles.core.agent` +
`veles.core.tools`, which left `reminder_runner`/`job_runner` warnings
to Python's lastResort stderr handler — they reached the same log file
via the spawn fd redirect but as bare, timestamp-less lines. The
handler is named (`veles-daemon-<slug>`) so repeated calls (tests,
hot-reloads) don't pile up duplicate handlers.

Level, rotation size, and backup count are configurable via the
`[daemon.logging]` section in `<project>/.veles/project.toml`. Env
`VELES_LOG_LEVEL` overrides everything for one-off debugging.

`truncate_for_log(text, cap)` is the project-wide helper for clipping
long tool args/results so the log file doesn't balloon when an agent
reads a 10MB file.

`install_stdio_funnel()` reassigns this (detached) process's
`sys.stdout`/`sys.stderr` to `_LoggerWriter` objects so raw output —
`print`, uncaught tracebacks, library retry storms — flows through the
same `RotatingFileHandler`. That makes the handler the *sole* writer to
the log file: rotation can no longer be defeated by a second, unrotated
raw-fd writer (the pre-existing `spawn.py` stdout redirect).
`should_funnel()` disables it in an interactive `--foreground` terminal
(TTY-guard) or via `VELES_LOG_NO_FUNNEL=1`; `logging.raiseExceptions=False`
plus a per-thread reentrancy guard stop a failing `emit()` from
livelocking through the funneled stderr under disk pressure.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

from veles.core.log_util import DEFAULT_TRUNCATE_CHARS, truncate_for_log
from veles.daemon.paths import daemon_log_path

_LOGGER_NAMES = (
    "veles.daemon",
    "veles.channels",
    "veles.cli.commands.daemon",
    # The whole core subtree — NOT individual `veles.core.*` children: a
    # handler on both a child and its ancestor would double-log every record
    # (propagation visits each handler once per logger in the chain).
    "veles.core",
)

DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10 MiB
DEFAULT_BACKUP_COUNT = 5
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


class _LoggerWriter:
    """File-like stand-in for `sys.stdout`/`sys.stderr` that turns raw writes
    into logging records.

    Line-buffers input and emits one record per complete line so a `print`
    or a traceback flows through the rotating file handler like any other log
    message — this is what makes the handler the *sole* writer to the daemon
    log (see `install_stdio_funnel`). Long lines are clipped so a library
    dumping a megabyte on one line can't blow up a single record.

    `fallback` is the original stream captured before reassignment. A write
    that re-enters `write()` on the same thread — the `logging.Handler.
    handleError` path writes the failing traceback to `sys.stderr`, which is
    now this object — is routed to `fallback` instead of back into logging,
    breaking the feedback livelock that would otherwise spin under disk
    pressure or a rotation failure.
    """

    def __init__(
        self,
        logger: logging.Logger,
        level: int,
        fallback: object,
        *,
        cap: int = DEFAULT_TRUNCATE_CHARS,
    ) -> None:
        self._logger = logger
        self._level = level
        self._fallback = fallback
        self._cap = cap
        self._buf = ""
        self._local = threading.local()
        # Guards the read-modify-write of `self._buf` below across threads.
        # The reentrancy guard above is per-thread (threading.local) and only
        # protects a thread against re-entering itself; it does nothing for
        # two *different* threads writing to this shared instance at once.
        # Without this lock, `self._logger.log()` can release the GIL for I/O
        # between the `"\n" in self._buf` check and the `.split("\n", 1)`
        # call, letting a second thread consume the buffer first and turning
        # the split into a `ValueError: not enough values to unpack`.
        self._lock = threading.Lock()

    def write(self, s: str) -> int:
        if getattr(self._local, "active", False):
            try:
                # Reentrant same-thread write (e.g. logging.Handler.handleError
                # writing its traceback to sys.stderr, which is this object).
                # This is a single, non-looping, non-size-bounded write to the
                # original stream — acceptable because it only fires on a
                # failing emit() and any error here is swallowed below. It
                # never touches `self._buf`/`self._lock`, so it cannot
                # deadlock against the locked branch below.
                writer = getattr(self._fallback, "write", None)
                if writer is not None:
                    writer(s)
            except Exception:
                pass
            return len(s)
        self._local.active = True
        try:
            with self._lock:
                self._buf += s
                while "\n" in self._buf:
                    line, self._buf = self._buf.split("\n", 1)
                    if line:
                        self._logger.log(self._level, truncate_for_log(line, self._cap))
            return len(s)
        finally:
            self._local.active = False

    def flush(self) -> None:
        if getattr(self._local, "active", False):
            # A reentrant flush (same thread, inside the write()/logging.log()
            # call above) is inert: the buffered remainder is intentionally
            # dropped here rather than emitted, because with
            # `logging.raiseExceptions = False` the real handleError path
            # never calls .flush() — this branch exists only as a defensive
            # guard, not a code path that fires in practice.
            return
        with self._lock:
            if not self._buf:
                return
            line, self._buf = self._buf, ""
        self._local.active = True
        try:
            self._logger.log(self._level, truncate_for_log(line, self._cap))
        finally:
            self._local.active = False

    def close(self) -> None:
        self.flush()

    def isatty(self) -> bool:
        return False


_TRUTHY = {"1", "true", "yes", "on"}


def should_funnel() -> bool:
    """True when it is safe and useful to redirect the process's
    stdout/stderr into logging.

    False when `VELES_LOG_NO_FUNNEL` is set (kill-switch) or when either fd 1
    or fd 2 is a TTY — an interactive `veles daemon start --foreground` in a
    real terminal must keep printing to the user's console. Uses `os.isatty`
    on the raw fds, not `sys.stdout.isatty()`, because the sys objects can be
    `None` or already replaced under detachment.
    """
    if os.environ.get("VELES_LOG_NO_FUNNEL", "").strip().lower() in _TRUTHY:
        return False
    try:
        if os.isatty(1) or os.isatty(2):
            return False
    except OSError:
        pass
    return True


_funnel_installed = False


def install_stdio_funnel() -> bool:
    """Redirect this process's stdout/stderr into logging so the rotating
    file handler becomes the single writer to the daemon log.

    No-op (returns False) when already installed or when `should_funnel()`
    declines (kill-switch / interactive terminal). Sets
    `logging.raiseExceptions = False` so a failing `emit()` during disk
    pressure cannot spew a traceback into the now-funneled stderr and
    livelock. Meant to be called once, in the daemon child, right after
    `setup_daemon_logging`.
    """
    global _funnel_installed
    if _funnel_installed or not should_funnel():
        return False
    orig_out, orig_err = sys.stdout, sys.stderr
    sys.stdout = _LoggerWriter(logging.getLogger("veles.daemon.stdout"), logging.INFO, orig_out)
    sys.stderr = _LoggerWriter(logging.getLogger("veles.daemon.stderr"), logging.WARNING, orig_err)
    logging.raiseExceptions = False
    _funnel_installed = True
    return True


def _uninstall_stdio_funnel() -> None:
    """Restore the pre-funnel stdout/stderr — test-only teardown.

    `_fallback` holds the original stream captured at install time.
    """
    global _funnel_installed
    if isinstance(sys.stdout, _LoggerWriter):
        sys.stdout = sys.stdout._fallback
    if isinstance(sys.stderr, _LoggerWriter):
        sys.stderr = sys.stderr._fallback
    _funnel_installed = False


__all__ = [
    "DEFAULT_TRUNCATE_CHARS",
    "install_stdio_funnel",
    "setup_daemon_logging",
    "should_funnel",
    "truncate_for_log",
]
