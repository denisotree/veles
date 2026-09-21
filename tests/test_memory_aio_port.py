"""M264: the async memory port, its bridge, and the bounded recall fan-out.

The bridge is the part that can deadlock a process rather than merely return a
wrong answer, so its refusals are tested as hard as its happy path.
"""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path

import pytest

from veles.core.memory import SessionStore, aio
from veles.core.memory.store import MemoryStore, SqliteStore, open_store
from veles.core.project import init_project

# ---- the bridge ----


def test_submit_returns_the_coroutine_result() -> None:
    async def work() -> int:
        await asyncio.sleep(0)
        return 7

    assert aio.submit(work()) == 7


def test_submit_reuses_one_loop_across_calls() -> None:
    """A loop per call would put loop construction on the recall hot path."""

    async def loop_id() -> int:
        return id(asyncio.get_running_loop())

    assert aio.submit(loop_id()) == aio.submit(loop_id())


def test_submit_runs_off_the_calling_thread() -> None:
    async def which_thread() -> int:
        return threading.get_ident()

    assert aio.submit(which_thread()) != threading.get_ident()


def test_submit_times_out_and_cancels() -> None:
    started = threading.Event()
    cancelled = threading.Event()

    async def slow() -> None:
        started.set()
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    t0 = time.perf_counter()
    with pytest.raises(TimeoutError):
        aio.submit(slow(), timeout=0.05)
    assert time.perf_counter() - t0 < 5.0  # the caller is not waiting out the sleep
    assert started.is_set()
    # The cancellation is delivered asynchronously; give the loop a moment.
    assert cancelled.wait(timeout=2.0)


def test_submit_refuses_to_block_a_running_loop() -> None:
    """Blocking the caller's own loop is a deadlock waiting for load. Refusing
    loudly beats a process that stops answering under it."""

    async def inner() -> None:
        return None

    async def outer() -> None:
        with pytest.raises(RuntimeError, match="inside an event loop"):
            aio.submit(inner())

    asyncio.run(outer())


# ---- the port ----


def test_open_store_satisfies_the_protocol(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    store = open_store(project)
    try:
        assert isinstance(store, MemoryStore)
        assert isinstance(store, SqliteStore)
    finally:
        aio.submit(store.close())


def test_port_reads_what_the_sync_store_wrote(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    sync = SessionStore(project.memory_db_path)
    try:
        sync._conn.execute(
            "INSERT INTO insights(title, body, category, created_at)"
            " VALUES ('t', 'redis ttl 300 session keys', 'test', 1000.0)"
        )
        sync._conn.commit()
    finally:
        sync.close()

    store = open_store(project)
    try:
        hits = aio.submit(store.search_insights("redis ttl", limit=5))
    finally:
        aio.submit(store.close())
    assert [h.title for h in hits] == ["t"]


def test_port_serialises_work_on_one_thread(tmp_path: Path) -> None:
    """Concurrent statements are allowed by sqlite3.threadsafety == 3, but the
    store keeps one worker so write ordering stays obvious."""
    project = init_project(tmp_path / "p", name="p")
    store = open_store(project)

    async def gather_thread_ids() -> set[int]:
        async def probe() -> int:
            return await store._run(threading.get_ident)

        return set(await asyncio.gather(*(probe() for _ in range(8))))

    try:
        assert len(aio.submit(gather_thread_ids())) == 1
    finally:
        aio.submit(store.close())


# ---- the bounded fan-out ----


def test_recall_keeps_what_finished_when_a_collector_hangs(tmp_path: Path, monkeypatch) -> None:
    """Partial beats empty. A slow source costs the deadline, not the turn, and
    the others still reach the prompt."""
    from veles.core.memory.router import MemoryRouter

    project = init_project(tmp_path / "p", name="p")
    store = SessionStore(project.memory_db_path)
    try:
        store._conn.execute(
            "INSERT INTO insights(title, body, category, created_at)"
            " VALUES ('fast', 'kafka consumer lag runbook', 'test', 1000.0)"
        )
        store._conn.commit()

        def hang(self, query: str, *, limit: int):
            time.sleep(30)
            return []

        monkeypatch.setattr(MemoryRouter, "_collect_wiki", hang)

        t0 = time.perf_counter()
        hits = MemoryRouter(project, store=store).recall("kafka consumer lag", deadline_sec=0.3)
        elapsed = time.perf_counter() - t0
    finally:
        store.close()

    assert elapsed < 5.0
    assert [h.title for h in hits] == ["fast"]


def test_recall_survives_a_failing_collector(tmp_path: Path, monkeypatch) -> None:
    from veles.core.memory.router import MemoryRouter

    project = init_project(tmp_path / "p", name="p")
    store = SessionStore(project.memory_db_path)
    try:
        store._conn.execute(
            "INSERT INTO insights(title, body, category, created_at)"
            " VALUES ('kept', 'postgres vacuum nightly', 'test', 1000.0)"
        )
        store._conn.commit()

        def boom(self, query: str, *, limit: int):
            raise RuntimeError("collector exploded")

        monkeypatch.setattr(MemoryRouter, "_collect_about_veles", boom)
        hits = MemoryRouter(project, store=store).recall("postgres vacuum")
    finally:
        store.close()

    assert [h.title for h in hits] == ["kept"]


def test_dropped_collector_does_not_age_its_rows(tmp_path: Path, monkeypatch) -> None:
    """`last_referenced_at` is the recency signal rerank scores on and the one
    dedup picks its canonical survivor by. A collector cancelled at the deadline
    must not bump it: those rows never reached the prompt, so calling them
    "referenced" corrupts both.
    """
    from veles.core.memory.router import MemoryRouter

    project = init_project(tmp_path / "p", name="p")
    store = SessionStore(project.memory_db_path)
    try:
        store._conn.execute(
            "INSERT INTO insights(title, body, category, created_at)"
            " VALUES ('slow', 'terraform state locking notes', 'test', 1000.0)"
        )
        store._conn.commit()
        real = MemoryRouter._collect_insights

        async def slow_insights(self, query: str, *, limit: int):
            hits = await real(self, query, limit=limit)
            await asyncio.sleep(30)
            return hits

        monkeypatch.setattr(MemoryRouter, "_collect_insights", slow_insights)
        MemoryRouter(project, store=store).recall("terraform state locking", deadline_sec=0.3)
        referenced = store._conn.execute(
            "SELECT last_referenced_at FROM insights WHERE title = 'slow'"
        ).fetchone()[0]
    finally:
        store.close()

    assert referenced is None


def test_recall_deadline_comes_from_config(tmp_path: Path, monkeypatch) -> None:
    """A multi-tenant deployment tunes this first, so it is a config key rather
    than a constant -- and a malformed value falls back instead of removing the
    bound, because "no deadline" must not be reachable by typo."""
    from veles.core.memory.router import _RECALL_DEADLINE_SEC, _load_recall_deadline

    project = init_project(tmp_path / "p", name="p")
    config = project.state_dir / "config.toml"

    config.write_text("[memory.recall]\ndeadline_sec = 0.25\n", encoding="utf-8")
    assert _load_recall_deadline(project) == pytest.approx(0.25)

    for broken in ("deadline_sec = 0\n", 'deadline_sec = "soon"\n', ""):
        config.write_text("[memory.recall]\n" + broken, encoding="utf-8")
        assert _load_recall_deadline(project) == _RECALL_DEADLINE_SEC
