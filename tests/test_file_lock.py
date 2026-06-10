"""M30 — advisory exclusive flock helper.

The lock must serialize concurrent threads in one process (per-fd
flock semantics) and survive exception unwind.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from veles.core.file_lock import file_lock


def test_serial_acquisitions_succeed(tmp_path: Path) -> None:
    lock = tmp_path / "x.lock"
    with file_lock(lock):
        pass
    with file_lock(lock):
        pass


def test_lock_file_created_in_missing_subdir(tmp_path: Path) -> None:
    lock = tmp_path / "subdir" / "x.lock"
    assert not lock.parent.exists()
    with file_lock(lock):
        assert lock.exists()


def test_lock_releases_on_exception(tmp_path: Path) -> None:
    lock = tmp_path / "x.lock"
    with pytest.raises(RuntimeError, match="boom"), file_lock(lock):
        raise RuntimeError("boom")
    # Re-acquirable — the lock was released on unwind.
    with file_lock(lock):
        pass


def test_parallel_threads_serialize_critical_section(tmp_path: Path) -> None:
    """8 threads x 100 non-atomic increments under the lock — no lost updates."""
    lock = tmp_path / "x.lock"
    counter = [0]
    iterations = 100
    workers = 8

    def worker() -> None:
        for _ in range(iterations):
            with file_lock(lock):
                v = counter[0]
                # Simulate non-atomic read-modify-write — without the lock
                # interleaving would lose updates.
                counter[0] = v + 1

    threads = [threading.Thread(target=worker) for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert counter[0] == workers * iterations


def test_distinct_lock_paths_do_not_block_each_other(tmp_path: Path) -> None:
    """Lock per path — two different lock files can be held simultaneously."""
    a = tmp_path / "a.lock"
    b = tmp_path / "b.lock"
    held_b = threading.Event()
    release_a = threading.Event()

    def hold_a() -> None:
        with file_lock(a):
            release_a.wait(timeout=2.0)

    def hold_b() -> None:
        with file_lock(b):
            held_b.set()

    ta = threading.Thread(target=hold_a)
    tb = threading.Thread(target=hold_b)
    ta.start()
    tb.start()
    # `b` must be acquired even while `a` is held.
    assert held_b.wait(timeout=2.0)
    release_a.set()
    ta.join()
    tb.join()
