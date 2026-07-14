"""Daemon stdio funnel: sys.stdout/stderr routed into the rotating handler."""

from __future__ import annotations

import io
import logging
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from veles.daemon.logging import _LoggerWriter, should_funnel


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[tuple[int, str]] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append((record.levelno, record.getMessage()))


def _wire(name: str) -> tuple[logging.Logger, _Capture]:
    log = logging.getLogger(name)
    cap = _Capture()
    log.addHandler(cap)
    log.setLevel(logging.DEBUG)
    log.propagate = False
    return log, cap


def test_write_buffers_partial_line_until_newline() -> None:
    log, cap = _wire("test.funnel.buffer")
    try:
        w = _LoggerWriter(log, logging.INFO, io.StringIO())
        w.write("hello ")
        assert cap.records == []  # no newline yet -> nothing emitted
        w.write("world\n")
        assert cap.records == [(logging.INFO, "hello world")]
    finally:
        log.removeHandler(cap)


def test_write_emits_multiple_lines_in_one_call() -> None:
    log, cap = _wire("test.funnel.multi")
    try:
        w = _LoggerWriter(log, logging.INFO, io.StringIO())
        w.write("a\nb\nc\n")
        assert [m for _, m in cap.records] == ["a", "b", "c"]
    finally:
        log.removeHandler(cap)


def test_blank_lines_are_skipped() -> None:
    log, cap = _wire("test.funnel.blank")
    try:
        w = _LoggerWriter(log, logging.INFO, io.StringIO())
        w.write("\n\nreal\n")
        assert [m for _, m in cap.records] == ["real"]
    finally:
        log.removeHandler(cap)


def test_level_is_respected() -> None:
    log, cap = _wire("test.funnel.level")
    try:
        w = _LoggerWriter(log, logging.WARNING, io.StringIO())
        w.write("warn-line\n")
        assert cap.records == [(logging.WARNING, "warn-line")]
    finally:
        log.removeHandler(cap)


def test_long_line_is_clipped() -> None:
    log, cap = _wire("test.funnel.clip")
    try:
        w = _LoggerWriter(log, logging.INFO, io.StringIO(), cap=100)
        w.write("x" * 5000 + "\n")
        msg = cap.records[0][1]
        assert msg.startswith("x" * 100)
        assert "truncated" in msg
    finally:
        log.removeHandler(cap)


def test_reentrant_write_goes_to_fallback_not_logging() -> None:
    """If the logger's emit path re-enters write() on the same thread (the
    handleError -> sys.stderr loop), the nested payload must land on the
    fallback stream and must NOT recurse into logging again."""
    fallback = io.StringIO()

    class _Reentering(logging.Handler):
        def __init__(self, writer_box: list) -> None:
            super().__init__()
            self.writer_box = writer_box
            self.calls = 0

        def emit(self, record: logging.LogRecord) -> None:
            self.calls += 1
            # Simulate handleError writing to sys.stderr == our writer.
            self.writer_box[0].write("nested-from-emit\n")

    box: list = []
    log = logging.getLogger("test.funnel.reentry")
    h = _Reentering(box)
    log.addHandler(h)
    log.setLevel(logging.DEBUG)
    log.propagate = False
    try:
        w = _LoggerWriter(log, logging.INFO, fallback)
        box.append(w)
        w.write("outer\n")
        # emit ran exactly once (no infinite recursion) and the nested write
        # was diverted to the fallback stream.
        assert h.calls == 1
        assert "nested-from-emit" in fallback.getvalue()
    finally:
        log.removeHandler(h)


def test_isatty_is_false() -> None:
    w = _LoggerWriter(logging.getLogger("test.funnel.tty"), logging.INFO, io.StringIO())
    assert w.isatty() is False


def test_should_funnel_true_when_not_tty_and_no_killswitch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("VELES_LOG_NO_FUNNEL", raising=False)
    monkeypatch.setattr("os.isatty", lambda fd: False)
    assert should_funnel() is True


def test_should_funnel_false_when_killswitch_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("os.isatty", lambda fd: False)
    for val in ("1", "true", "YES", "on"):
        monkeypatch.setenv("VELES_LOG_NO_FUNNEL", val)
        assert should_funnel() is False


def test_should_funnel_false_when_stdout_is_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VELES_LOG_NO_FUNNEL", raising=False)
    monkeypatch.setattr("os.isatty", lambda fd: fd == 1)
    assert should_funnel() is False


def test_should_funnel_false_when_stderr_is_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VELES_LOG_NO_FUNNEL", raising=False)
    monkeypatch.setattr("os.isatty", lambda fd: fd == 2)
    assert should_funnel() is False


def test_should_funnel_true_when_isatty_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VELES_LOG_NO_FUNNEL", raising=False)

    def _boom(fd: int) -> bool:
        raise OSError("bad fd")

    monkeypatch.setattr("os.isatty", _boom)
    assert should_funnel() is True


def test_concurrent_writes_do_not_crash_or_lose_lines() -> None:
    """Two different threads writing to a single shared `_LoggerWriter` must
    not corrupt `self._buf`: the reentrancy guard is per-thread
    (threading.local) so it does nothing to serialize cross-thread access.
    Without the lock in `write()`, `logger.log()` doing I/O between the
    newline check and the `.split("\n", 1)` call lets a second thread race
    the buffer and raise `ValueError: not enough values to unpack`."""
    import threading

    log, cap = _wire("test.funnel.concurrent")
    try:
        w = _LoggerWriter(log, logging.INFO, io.StringIO())
        n_threads, n_lines = 8, 200
        barrier = threading.Barrier(n_threads)
        errors: list[BaseException] = []

        def worker(tid: int) -> None:
            barrier.wait()
            try:
                for i in range(n_lines):
                    w.write(f"t{tid}-line-{i}\n")
            except BaseException as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        assert len(cap.records) == n_threads * n_lines
    finally:
        log.removeHandler(cap)


@pytest.fixture
def _restore_stdio() -> Iterator[None]:
    saved_out, saved_err = sys.stdout, sys.stderr
    saved_raise = logging.raiseExceptions
    yield
    from veles.daemon.logging import _uninstall_stdio_funnel

    _uninstall_stdio_funnel()
    sys.stdout, sys.stderr = saved_out, saved_err
    logging.raiseExceptions = saved_raise


def test_install_replaces_stdio_and_disables_raise(
    monkeypatch: pytest.MonkeyPatch, _restore_stdio: None
) -> None:
    from veles.daemon.logging import install_stdio_funnel

    monkeypatch.delenv("VELES_LOG_NO_FUNNEL", raising=False)
    monkeypatch.setattr("os.isatty", lambda fd: False)
    assert install_stdio_funnel() is True
    assert type(sys.stdout).__name__ == "_LoggerWriter"
    assert type(sys.stderr).__name__ == "_LoggerWriter"
    assert logging.raiseExceptions is False


def test_install_is_idempotent(monkeypatch: pytest.MonkeyPatch, _restore_stdio: None) -> None:
    from veles.daemon.logging import install_stdio_funnel

    monkeypatch.delenv("VELES_LOG_NO_FUNNEL", raising=False)
    monkeypatch.setattr("os.isatty", lambda fd: False)
    assert install_stdio_funnel() is True
    first = sys.stdout
    assert install_stdio_funnel() is False  # second call is a no-op
    assert sys.stdout is first


def test_install_skips_when_should_funnel_false(
    monkeypatch: pytest.MonkeyPatch, _restore_stdio: None
) -> None:
    from veles.daemon.logging import install_stdio_funnel

    monkeypatch.setenv("VELES_LOG_NO_FUNNEL", "1")
    before = sys.stdout
    assert install_stdio_funnel() is False
    assert sys.stdout is before


def test_funneled_stdout_rotates_through_handler(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Integration: writes through the stdout logger flow into the rotating
    file handler and produce a `.1` backup once the tiny budget overflows —
    without ever touching the process's real sys.stdout."""
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "veles"))
    from veles.daemon.logging import _LoggerWriter, setup_daemon_logging

    log_path = setup_daemon_logging("alpha", max_bytes=512, backup_count=2)
    try:
        w = _LoggerWriter(logging.getLogger("veles.daemon.stdout"), logging.INFO, io.StringIO())
        for i in range(200):
            w.write(f"noisy-line-{i:04d}: {'x' * 80}\n")
        for h in logging.getLogger("veles.daemon").handlers:
            h.flush()
        assert log_path.is_file()
        assert log_path.with_suffix(".log.1").is_file()
    finally:
        for h in list(logging.getLogger("veles.daemon").handlers):
            if (h.get_name() or "").startswith("veles-daemon-"):
                logging.getLogger("veles.daemon").removeHandler(h)


def test_bootstrap_daemon_installs_funnel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`_bootstrap_daemon` must call install_stdio_funnel after setting up
    logging, so a detached daemon's raw output is captured by rotation."""
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "veles"))

    called: list[bool] = []
    import veles.cli.commands.daemon_lifecycle as lifecycle

    monkeypatch.setattr(lifecycle, "_setup_daemon_logging", lambda *a, **k: tmp_path / "x.log")
    monkeypatch.setattr(
        "veles.daemon.logging.install_stdio_funnel", lambda: called.append(True) or True
    )

    class _Proj:
        name = "alpha"
        root = tmp_path

    monkeypatch.setattr("veles.core.context.set_active_project", lambda p: None)
    monkeypatch.setattr("veles.cli._load_project_modules", lambda p: {})
    monkeypatch.setattr("veles.core.modules.set_module_registry", lambda r: None)
    monkeypatch.setattr(lifecycle.os, "chdir", lambda p: None)
    monkeypatch.setattr("veles.core.project_config.load_project_config", lambda p: {})
    monkeypatch.setattr("veles.core.project_config.get_section", lambda cfg, *k: {})
    monkeypatch.setattr(lifecycle, "_install_daemon_critical_confirmer", lambda: None)

    lifecycle._bootstrap_daemon(_Proj(), name=None)
    assert called == [True]
