"""M110: file-backed logging for the daemon + log-path resolution.

The daemon's previous lifecycle messages went to sys.stderr inside a
detached subprocess (Popen stdout/stderr redirected to DEVNULL), so they
were unrecoverable. Now they land in ~/.veles/logs/daemon-<slug>.log via
a RotatingFileHandler wired up in `_cmd_daemon_start`.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from veles.daemon.logging import setup_daemon_logging as _setup_daemon_logging
from veles.daemon.paths import daemon_log_path


@pytest.fixture(autouse=True)
def _isolate_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "veles"))
    yield tmp_path
    # Each test rewires loggers; tear down so we don't leak between tests.
    for name in (
        "veles.daemon",
        "veles.channels",
        "veles.cli.commands.daemon",
        "veles.core.agent",
        "veles.core.tools",
    ):
        log = logging.getLogger(name)
        for h in list(log.handlers):
            if (h.get_name() or "").startswith("veles-daemon-"):
                log.removeHandler(h)


def test_log_path_resolves_under_user_home(tmp_path: Path) -> None:
    path = daemon_log_path("alpha")
    assert path.name == "daemon-alpha.log"
    assert path.parent.name == "logs"


def test_setup_creates_log_dir_and_file(tmp_path: Path) -> None:
    log_path = _setup_daemon_logging("alpha")
    assert log_path.parent.is_dir()
    # Emit a record and flush so it lands in the file synchronously.
    log = logging.getLogger("veles.daemon")
    log.info("hello-from-daemon")
    for h in log.handlers:
        h.flush()
    assert log_path.is_file()
    assert "hello-from-daemon" in log_path.read_text(encoding="utf-8")


def test_setup_is_idempotent_no_duplicate_handlers(tmp_path: Path) -> None:
    """Calling _setup_daemon_logging twice with the same slug must not
    double-emit each log line."""
    _setup_daemon_logging("alpha")
    _setup_daemon_logging("alpha")
    log = logging.getLogger("veles.daemon")
    tagged = [h for h in log.handlers if (h.get_name() or "").startswith("veles-daemon-alpha")]
    assert len(tagged) == 1


def test_channels_logger_writes_to_same_file(tmp_path: Path) -> None:
    """Daemon log captures channel events (Telegram, future channels) as
    well — they share the file handler under `veles.channels`."""
    log_path = _setup_daemon_logging("alpha")
    logging.getLogger("veles.channels.telegram").info("telegram-event-XYZ")
    for h in logging.getLogger("veles.channels").handlers:
        h.flush()
    assert "telegram-event-XYZ" in log_path.read_text(encoding="utf-8")


def test_level_from_argument_enables_debug(tmp_path: Path) -> None:
    """`[daemon.logging] level = "DEBUG"` lets the agent's per-step
    diagnostics through; the default INFO swallows them."""
    log_path = _setup_daemon_logging("alpha", level="DEBUG")
    log = logging.getLogger("veles.daemon")
    log.debug("debug-line-1")
    for h in log.handlers:
        h.flush()
    assert "debug-line-1" in log_path.read_text(encoding="utf-8")


def test_env_log_level_overrides_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A one-off `VELES_LOG_LEVEL=DEBUG veles daemon start` beats whatever
    is sitting in project.toml."""
    monkeypatch.setenv("VELES_LOG_LEVEL", "DEBUG")
    log_path = _setup_daemon_logging("alpha", level="ERROR")
    log = logging.getLogger("veles.daemon")
    log.debug("env-debug-XYZ")
    for h in log.handlers:
        h.flush()
    assert "env-debug-XYZ" in log_path.read_text(encoding="utf-8")


def test_truncate_for_log_caps_long_payloads() -> None:
    from veles.daemon.logging import truncate_for_log

    long = "x" * 5000
    out = truncate_for_log(long, cap=100)
    assert out.startswith("x" * 100)
    assert "truncated" in out
    assert "5000" in out
    # Short input passes through untouched.
    assert truncate_for_log("hi", cap=100) == "hi"
    assert truncate_for_log(None) == ""


def test_tool_call_lands_in_daemon_log(tmp_path: Path) -> None:
    """End-to-end: agent dispatches a tool → daemon log carries
    `tool.call name=… args=…` and `tool.result name=… preview=…`."""
    log_path = _setup_daemon_logging("alpha")
    agent_log = logging.getLogger("veles.core.agent")
    agent_log.info("tool.call name=demo args={'x': 1}")
    agent_log.info("tool.result name=demo preview=ok")
    for h in agent_log.handlers:
        h.flush()
    body = log_path.read_text(encoding="utf-8")
    assert "tool.call name=demo" in body
    assert "tool.result name=demo" in body


def test_rotation_respects_args(tmp_path: Path) -> None:
    """Tiny rotation budget — once we exceed it, a `.1` backup must
    appear and the main file restarts from scratch."""
    log_path = _setup_daemon_logging("alpha", max_bytes=512, backup_count=2)
    log = logging.getLogger("veles.daemon")
    for i in range(100):
        log.info("line-%03d: %s", i, "x" * 80)
    for h in log.handlers:
        h.flush()
    assert log_path.is_file()
    assert log_path.with_suffix(".log.1").is_file()
