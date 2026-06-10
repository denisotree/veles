"""Iterator over a subprocess's line-delimited JSON stdout.

Used by claude-cli and gemini-cli `stream_message` to consume
`--output-format stream-json` lazily so TextDelta events can be emitted as
soon as the underlying CLI flushes them.

Stderr is drained concurrently on a daemon thread into a bounded tail
buffer (last ~64KB). Reading it only after stdout EOF — the previous
implementation — deadlocked whenever the child filled the OS stderr pipe
buffer (>64KB) while still producing stdout: the child blocked on
`write(2)`, the parent blocked on stdout `readline`. The error contract
is uniform: **any** failure (nonzero exit, mid-stream timeout, or the
child failing to exit after stdout EOF) raises ``RuntimeError`` carrying
the reason and the stderr *tail* — so a caller's ``except RuntimeError``
handles every failure mode the same way (no stray ``TimeoutExpired``
escapes to crash the consumer).
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
from collections import deque
from collections.abc import Iterator
from typing import Any

# How much trailing stderr to keep for the nonzero-exit error message.
_STDERR_TAIL_LIMIT = 64 * 1024
_STDERR_CHUNK = 8192


def popen_jsonl(
    cmd: list[str],
    *,
    timeout: float,
    cwd: str | None = None,
) -> Iterator[dict[str, Any]]:
    """Spawn `cmd` and yield each parsed JSON line from its stdout.

    `timeout` bounds both the final `wait()` and — checked per received
    line — the stdout read loop: if the overall deadline passes while
    lines are still arriving, the child is killed and the failure is
    reported as ``RuntimeError`` (same contract as a nonzero exit). (A
    child that goes fully silent without closing stdout still blocks in
    `readline`; bounding that would require non-blocking I/O and is out
    of contract here, so the worst-case wall-clock is ~2×timeout.)
    """
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        cwd=cwd,
    )

    stderr_tail: deque[str] = deque()
    # Guards `stderr_tail`: the drain thread appends/pops while the main
    # thread reads the tail on the error path. Without it, the read could
    # iterate the deque mid-mutation (`RuntimeError: deque mutated`),
    # masking the real failure.
    tail_lock = threading.Lock()

    def _drain_stderr() -> None:
        stream = proc.stderr
        if stream is None:
            return
        kept = 0
        try:
            while True:
                chunk = stream.read(_STDERR_CHUNK)  # blocking read, outside the lock
                if not chunk:
                    break
                with tail_lock:
                    stderr_tail.append(chunk)
                    kept += len(chunk)
                    while kept > _STDERR_TAIL_LIMIT and len(stderr_tail) > 1:
                        kept -= len(stderr_tail.popleft())
        except (OSError, ValueError):
            pass  # pipe closed under us during teardown — tail stays as-is

    drainer = threading.Thread(
        target=_drain_stderr, name="popen-jsonl-stderr-drain", daemon=True
    )
    drainer.start()

    def _stderr_tail() -> str:
        """Snapshot the drained stderr tail for an error message. Join the
        drainer first — it exits once stderr EOFs, which the child's exit
        (normal, killed, or terminated) guarantees — then read under the
        lock so we never iterate the deque while it's still being mutated."""
        drainer.join(timeout=5.0)
        with tail_lock:
            return "".join(stderr_tail).strip() or "<no stderr>"

    deadline = time.monotonic() + timeout
    try:
        assert proc.stdout is not None
        for raw in proc.stdout:
            if time.monotonic() > deadline:
                proc.kill()
                raise RuntimeError(
                    f"{cmd[0]} timed out after {timeout:.0f}s: {_stderr_tail()}"
                )
            line = raw.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue
        try:
            rc = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            raise RuntimeError(
                f"{cmd[0]} did not exit within {timeout:.0f}s after stdout EOF: "
                f"{_stderr_tail()}"
            ) from None
        if rc != 0:
            raise RuntimeError(f"{cmd[0]} exited {rc}: {_stderr_tail()}")
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                proc.kill()
