"""Unit tests for `_streaming.popen_jsonl`."""

from __future__ import annotations

import io
import subprocess
import sys
import threading

import pytest

from veles.adapters.cli._streaming import popen_jsonl


class _FakePopen:
    def __init__(self, stdout_lines: list[str], *, returncode: int = 0, stderr: str = "") -> None:
        self.stdout = io.StringIO("".join(stdout_lines))
        self.stderr = io.StringIO(stderr)
        self._rc = returncode
        self.returncode = returncode
        self._terminated = False

    def wait(self, timeout: float | None = None) -> int:
        self.returncode = self._rc
        return self._rc

    def poll(self) -> int | None:
        return self._rc

    def terminate(self) -> None:
        self._terminated = True

    def kill(self) -> None:
        self._terminated = True


def _patch_popen(monkeypatch, stdout_lines: list[str], **kwargs) -> None:
    fake = _FakePopen(stdout_lines, **kwargs)

    def factory(*_a, **_k):
        return fake

    monkeypatch.setattr(subprocess, "Popen", factory)


def test_popen_jsonl_yields_parsed_events(monkeypatch) -> None:
    lines = ['{"type":"a"}\n', '{"type":"b","x":1}\n', '{"type":"c"}\n']
    _patch_popen(monkeypatch, lines)
    out = list(popen_jsonl(["fake"], timeout=5.0))
    assert [e["type"] for e in out] == ["a", "b", "c"]
    assert out[1]["x"] == 1


def test_popen_jsonl_skips_blank_and_invalid(monkeypatch) -> None:
    lines = ['{"type":"a"}\n', "\n", "not json\n", '{"type":"b"}\n']
    _patch_popen(monkeypatch, lines)
    out = list(popen_jsonl(["fake"], timeout=5.0))
    assert [e["type"] for e in out] == ["a", "b"]


def test_popen_jsonl_raises_on_nonzero_exit(monkeypatch) -> None:
    _patch_popen(monkeypatch, ['{"type":"a"}\n'], returncode=2, stderr="boom")
    with pytest.raises(RuntimeError, match=r"fake exited 2.*boom"):
        list(popen_jsonl(["fake"], timeout=5.0))


# ---- real-subprocess regression tests (M151 stderr-deadlock fix) ----

# Interleaves several flushed JSONL stdout lines with ~128KB of stderr —
# more than any platform's pipe buffer. Before the concurrent stderr
# drain, the child blocked on a full stderr pipe while the parent blocked
# on stdout readline: a mutual deadlock.
_NOISY_CHILD = (
    "import sys\n"
    "blob = 'x' * 16384\n"
    "for i in range(8):\n"
    "    sys.stdout.write('{\"n\": %d}\\n' % i)\n"
    "    sys.stdout.flush()\n"
    "    sys.stderr.write(blob)\n"
    "    sys.stderr.flush()\n"
)


def test_popen_jsonl_drains_large_stderr_without_deadlock() -> None:
    """>100KB of stderr while stdout is still streaming must not deadlock.

    Consumption runs on a daemon thread with a bounded join so a
    regression fails fast instead of hanging the test session.
    """
    results: list[dict] = []
    errors: list[BaseException] = []

    def consume() -> None:
        try:
            results.extend(popen_jsonl([sys.executable, "-c", _NOISY_CHILD], timeout=30.0))
        except BaseException as exc:  # relayed to the assert below
            errors.append(exc)

    t = threading.Thread(target=consume, daemon=True)
    t.start()
    t.join(timeout=60.0)
    assert not t.is_alive(), "popen_jsonl deadlocked while child filled stderr"
    assert errors == []
    assert [e["n"] for e in results] == list(range(8))


def test_popen_jsonl_timeout_surfaces_as_runtimeerror() -> None:
    """A run that overruns the deadline while still emitting lines must
    raise ``RuntimeError`` — never a bare ``subprocess.TimeoutExpired``.

    The claude-cli / gemini-cli consumers only ``except RuntimeError``;
    pre-fix the deadline branch raised ``TimeoutExpired`` (not a
    ``RuntimeError`` subclass), so it escaped the consumer and crashed the
    stream instead of degrading to a ``StreamEnd(error=…)``. This test
    fails on the old code because ``pytest.raises(RuntimeError)`` would
    not catch the escaping ``TimeoutExpired``.
    """
    child = (
        "import sys, time\n"
        "sys.stdout.write('{\"n\": 0}\\n'); sys.stdout.flush()\n"
        "time.sleep(1.0)\n"  # the next line arrives well past the 0.3s deadline
        "sys.stdout.write('{\"n\": 1}\\n'); sys.stdout.flush()\n"
    )
    results: list[dict] = []
    with pytest.raises(RuntimeError, match=r"timed out"):
        for ev in popen_jsonl([sys.executable, "-c", child], timeout=0.3):
            results.append(ev)
    # first line was delivered before the deadline; then the child is killed.
    assert [e["n"] for e in results] == [0]


def test_popen_jsonl_stderr_tail_reaches_error_on_nonzero_exit() -> None:
    """Nonzero exit after huge stderr: error carries the stderr *tail*."""
    child = (
        "import sys\n"
        'sys.stdout.write(\'{"type": "a"}\\n\')\n'
        "sys.stdout.flush()\n"
        "sys.stderr.write('padding' * 20000)\n"  # ~137KB, exceeds the 64KB tail
        "sys.stderr.write('FATAL-MARKER')\n"
        "sys.exit(3)\n"
    )
    with pytest.raises(RuntimeError) as excinfo:
        list(popen_jsonl([sys.executable, "-c", child], timeout=30.0))
    msg = str(excinfo.value)
    assert "exited 3" in msg
    assert "FATAL-MARKER" in msg  # the tail (not the head) survives truncation
