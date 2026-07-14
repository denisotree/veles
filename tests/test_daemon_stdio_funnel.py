"""Daemon stdio funnel: sys.stdout/stderr routed into the rotating handler."""

from __future__ import annotations

import io
import logging

from veles.daemon.logging import _LoggerWriter


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
