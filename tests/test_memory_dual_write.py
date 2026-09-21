"""M265: writing an insight out to an external memory engine.

The contract under test is not "the write happens" — it is what happens when it
does *not*. Best-effort is only meaningful if the failures are recoverable, so
these tests spend most of their effort on the unhappy paths.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from veles.core.memory import SessionStore
from veles.core.memory.dual_write import push_insight, resync_pending
from veles.core.memory.provider import IngestingMemoryProvider, MemoryProvider
from veles.core.memory.router import RecallHit
from veles.core.project import init_project
from veles.core.tools.builtin.memory_save import save_insight_row


class _Recorder:
    """An ingesting provider that remembers what it was handed."""

    name = "recorder"

    def __init__(self, *, accept: bool = True, explode: bool = False) -> None:
        self.accept = accept
        self.explode = explode
        self.seen: list[tuple[int, str]] = []

    def recall(self, query: str, *, limit: int) -> list[RecallHit]:
        return []

    def ingest(self, title: str, body: str, *, insight_id: int) -> bool:
        if self.explode:
            raise RuntimeError("engine unreachable")
        self.seen.append((insight_id, title))
        return self.accept


class _ReadOnly:
    """The shape the three shipped adapters have: recall, no ingest."""

    name = "read-only"

    def recall(self, query: str, *, limit: int) -> list[RecallHit]:
        return []


def _synced_at(project, insight_id: int) -> float | None:
    conn = sqlite3.connect(str(project.memory_db_path))
    try:
        return conn.execute(
            "SELECT synced_at FROM insights WHERE id = ?", (insight_id,)
        ).fetchone()[0]
    finally:
        conn.close()


def _insert(project, title: str, body: str) -> int:
    store = SessionStore(project.memory_db_path)
    try:
        cur = store._conn.execute(
            "INSERT INTO insights(title, body, category, created_at) VALUES (?, ?, 'test', ?)",
            (title, body, time.time()),
        )
        store._conn.commit()
        return int(cur.lastrowid or 0)
    finally:
        store.close()


def _use(monkeypatch, providers: list[object]) -> None:
    monkeypatch.setattr(
        "veles.core.memory.providers.build_extra_providers", lambda: providers, raising=False
    )


# ---- the protocol ----


def test_ingest_is_optional() -> None:
    """A recall-only provider stays valid: the three shipped adapters are that
    shape, and requiring `ingest` would have broken all of them."""
    assert isinstance(_ReadOnly(), MemoryProvider)
    assert not isinstance(_ReadOnly(), IngestingMemoryProvider)
    assert isinstance(_Recorder(), IngestingMemoryProvider)


# ---- the write path ----


def test_saving_an_insight_offers_it_to_the_engine(tmp_path: Path, monkeypatch) -> None:
    project = init_project(tmp_path / "p", name="p")
    recorder = _Recorder()
    _use(monkeypatch, [recorder, _ReadOnly()])

    rid = save_insight_row(title="ttl", body="redis ttl is 300s", category="t", project=project)

    assert rid > 0
    assert recorder.seen == [(rid, "ttl")]
    assert _synced_at(project, rid) is not None


def test_a_failing_engine_does_not_lose_the_fact(tmp_path: Path, monkeypatch) -> None:
    """The local row is the source of truth. An unreachable engine must cost
    nothing but a NULL `synced_at` — not the insight, and not the turn."""
    project = init_project(tmp_path / "p", name="p")
    _use(monkeypatch, [_Recorder(explode=True)])

    rid = save_insight_row(
        title="kept", body="postgres vacuums nightly", category="t", project=project
    )

    assert rid > 0
    store = SessionStore(project.memory_db_path)
    try:
        body = store._conn.execute("SELECT body FROM insights WHERE id = ?", (rid,)).fetchone()[0]
    finally:
        store.close()
    assert body == "postgres vacuums nightly"
    assert _synced_at(project, rid) is None  # findable as unsynced


def test_no_engine_configured_is_not_an_error(tmp_path: Path, monkeypatch) -> None:
    project = init_project(tmp_path / "p", name="p")
    _use(monkeypatch, [])
    rid = save_insight_row(title="solo", body="local only", category="t", project=project)
    assert rid > 0
    assert _synced_at(project, rid) is None


def test_rejected_write_is_not_marked_synced(tmp_path: Path, monkeypatch) -> None:
    """A provider that answers "no" is different from one that throws, and both
    must leave the row retryable."""
    project = init_project(tmp_path / "p", name="p")
    _use(monkeypatch, [_Recorder(accept=False)])
    rid = _insert(project, "declined", "engine said no")
    assert push_insight(project, insight_id=rid, title="declined", body="engine said no") is False
    assert _synced_at(project, rid) is None


# ---- the resync ----


def test_resync_offers_only_what_never_arrived(tmp_path: Path, monkeypatch) -> None:
    project = init_project(tmp_path / "p", name="p")
    failing = _Recorder(explode=True)
    _use(monkeypatch, [failing])
    missed = save_insight_row(
        title="missed", body="kafka lag runbook", category="t", project=project
    )

    recorder = _Recorder()
    _use(monkeypatch, [recorder])
    landed = save_insight_row(title="landed", body="nginx tuning", category="t", project=project)

    recorder.seen.clear()
    assert resync_pending(project) == 1
    assert [i for i, _ in recorder.seen] == [missed]  # the one that already arrived is left alone
    assert _synced_at(project, missed) is not None
    assert _synced_at(project, landed) is not None


def test_resync_skips_hidden_insights(tmp_path: Path, monkeypatch) -> None:
    """A fact removed from recall should not be pushed into an external engine
    afterwards — that would reintroduce it somewhere Veles no longer shows it."""
    from veles.core.memory import hide_insight

    project = init_project(tmp_path / "p", name="p")
    rid = _insert(project, "retracted", "an old wrong fact")
    store = SessionStore(project.memory_db_path)
    try:
        hide_insight(store._conn, rid, reason="user-retracted")
        store._conn.commit()
    finally:
        store.close()

    recorder = _Recorder()
    _use(monkeypatch, [recorder])
    assert resync_pending(project) == 0
    assert recorder.seen == []


def test_resync_is_bounded(tmp_path: Path, monkeypatch) -> None:
    """A backlog drains over several cycles rather than turning one idle moment
    into a long network burst."""
    project = init_project(tmp_path / "p", name="p")
    for i in range(7):
        _insert(project, f"n{i}", f"body {i}")
    recorder = _Recorder()
    _use(monkeypatch, [recorder])
    assert resync_pending(project, limit=3) == 3
    assert len(recorder.seen) == 3


def test_dream_runs_the_resync(tmp_path: Path, monkeypatch) -> None:
    from veles.core.dreaming import dream_cycle

    project = init_project(tmp_path / "p", name="p")
    _insert(project, "pending", "never pushed")
    recorder = _Recorder()
    _use(monkeypatch, [recorder])

    result = dream_cycle(project, include_consolidation=False)

    assert len(recorder.seen) == 1
    assert any("memory-resync" in n for n in result.notes)


@pytest.mark.parametrize("explode", [True, False])
def test_push_never_raises(tmp_path: Path, monkeypatch, explode: bool) -> None:
    project = init_project(tmp_path / "p", name="p")
    _use(monkeypatch, [_Recorder(explode=explode)])
    rid = _insert(project, "t", "b")
    push_insight(project, insight_id=rid, title="t", body="b")  # must not raise


# ---- M265: the remote backend ----


def test_backend_defaults_to_sqlite(tmp_path: Path) -> None:
    from veles.core.memory import aio
    from veles.core.memory.store import SqliteStore, open_store

    project = init_project(tmp_path / "p", name="p")
    store = open_store(project)
    try:
        assert isinstance(store, SqliteStore)
    finally:
        aio.submit(store.close())


def test_remote_backend_without_a_provider_falls_back(tmp_path: Path, monkeypatch) -> None:
    """Starting a project with no memory at all is worse than starting it with
    local memory and a warning."""
    from veles.core.memory import aio
    from veles.core.memory.store import SqliteStore, open_store

    project = init_project(tmp_path / "p", name="p")
    (project.state_dir / "config.toml").write_text(
        '[memory.store]\nbackend = "remote"\n', encoding="utf-8"
    )
    _use(monkeypatch, [])
    store = open_store(project)
    try:
        assert isinstance(store, SqliteStore)
    finally:
        aio.submit(store.close())


def test_remote_backend_reads_insights_from_the_provider(tmp_path: Path, monkeypatch) -> None:
    from veles.core.memory import aio
    from veles.core.memory.store import RemoteStore, open_store

    class _Engine(_Recorder):
        def recall(self, query: str, *, limit: int) -> list[RecallHit]:
            return [RecallHit(rel_path="remote:1", title="from engine", summary="a remote fact")]

    project = init_project(tmp_path / "p", name="p")
    (project.state_dir / "config.toml").write_text(
        '[memory.store]\nbackend = "remote"\n', encoding="utf-8"
    )
    # A local row exists and must NOT be what comes back: the point of the
    # remote backend is that insights stop being served from the local file.
    _insert(project, "local", "a local fact")
    _use(monkeypatch, [_Engine()])

    store = open_store(project)
    try:
        assert isinstance(store, RemoteStore)
        hits = aio.submit(store.search_insights("anything", limit=5))
        assert [h.title for h in hits] == ["from engine"]
        # Remote hits carry no local row id, so aging must not touch anything.
        aio.submit(store.touch_insights([h.id for h in hits], 123.0))
    finally:
        aio.submit(store.close())

    conn = sqlite3.connect(str(project.memory_db_path))
    try:
        referenced = conn.execute("SELECT last_referenced_at FROM insights").fetchall()
    finally:
        conn.close()
    assert referenced == [(None,)]


def test_remote_backend_serves_the_recall_path(tmp_path: Path, monkeypatch) -> None:
    """The unit test above proves `RemoteStore.search_insights` works. This one
    proves the router actually calls it — the gap where a remote backend can be
    configured, constructed, and then quietly bypassed on the one path it
    exists for.
    """
    from veles.cli._runtime import _recall_block

    class _Engine(_Recorder):
        def recall(self, query: str, *, limit: int) -> list[RecallHit]:
            return [RecallHit(rel_path="remote:7", title="engine fact", summary="from the engine")]

    project = init_project(tmp_path / "p", name="p")
    (project.state_dir / "config.toml").write_text(
        '[memory.store]\nbackend = "remote"\n', encoding="utf-8"
    )
    _insert(project, "local fact", "kafka consumer lag runbook")
    _use(monkeypatch, [_Engine()])
    monkeypatch.setattr(
        "veles.core.memory.providers.builder.build_extra_providers", lambda: [], raising=False
    )

    block = _recall_block(project, "kafka consumer lag")

    assert block is not None
    assert "engine fact" in block
    assert "local fact" not in block  # insights come from the engine now, not the file


def test_the_row_is_committed_before_the_engine_sees_it(tmp_path: Path, monkeypatch) -> None:
    """Local-first is the whole contract, and nothing else here pins the
    ordering: if a refactor moved the push above the commit, every other test
    would still pass while the invariant was gone. This provider reads the row
    back from disk and fails if it is not already there."""
    seen_body: list[str | None] = []

    class _ReadsBack(_Recorder):
        def __init__(self, project) -> None:
            super().__init__()
            self._project = project

        def ingest(self, title: str, body: str, *, insight_id: int) -> bool:
            conn = sqlite3.connect(str(self._project.memory_db_path))
            try:
                row = conn.execute(
                    "SELECT body FROM insights WHERE id = ?", (insight_id,)
                ).fetchone()
            finally:
                conn.close()
            seen_body.append(row[0] if row else None)
            return True

    project = init_project(tmp_path / "p", name="p")
    _use(monkeypatch, [_ReadsBack(project)])
    save_insight_row(title="ordered", body="committed first", category="t", project=project)

    assert seen_body == ["committed first"]


def test_resync_builds_the_provider_list_once(tmp_path: Path, monkeypatch) -> None:
    project = init_project(tmp_path / "p", name="p")
    for i in range(5):
        _insert(project, f"n{i}", f"body {i}")

    builds = 0
    recorder = _Recorder()

    def counting_build() -> list[object]:
        nonlocal builds
        builds += 1
        return [recorder]

    monkeypatch.setattr(
        "veles.core.memory.providers.build_extra_providers", counting_build, raising=False
    )
    assert resync_pending(project) == 5
    assert builds == 1
