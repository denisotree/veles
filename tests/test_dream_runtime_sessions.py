"""M135-dream (ISSUES 3a): all launched runtime sessions (incl. soft-deleted)
feed an active daemon's dream.

`runtime_session_digest` renders every runtime_sessions record; `dream_cycle`
with a `runtime_session_loader` persists that snapshot into the learnable
`insights` corpus (category `daemon-fleet`, one living row replaced each cycle)
so a deleted daemon session's existence isn't lost to the learning loop.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from veles.core.dreaming import dream_cycle
from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.core.runtime_sessions import RuntimeSessionStore, runtime_session_digest

# ---- digest (pure) ----


def test_digest_none_when_empty():
    assert runtime_session_digest([]) is None


def test_digest_includes_active_and_deleted(tmp_path: Path):
    store = RuntimeSessionStore(tmp_path / "m.db")
    store.create("api", "daemon", provider="ollama", model="qwen3", port=8801)
    gone = store.create("old", "daemon", port=8802)
    store.soft_delete(gone.id)
    records = store.list(include_deleted=True)
    store.close()

    digest = runtime_session_digest(records)
    assert "**api** (daemon)" in digest
    assert "ollama:qwen3" in digest
    assert "**old** (daemon) — DELETED" in digest


# ---- dream step ----


def _fleet_rows(db_path: Path) -> list[tuple[str, str]]:
    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute(
            "SELECT title, body FROM insights WHERE category = 'daemon-fleet'"
        ).fetchall()
    finally:
        conn.close()


def test_dream_cycle_records_fleet_snapshot(tmp_path: Path):
    project = init_project(tmp_path / "p", name="p")
    SessionStore(project.memory_db_path).close()  # ensure insights schema exists

    result = dream_cycle(
        project,
        skip_insights=True,
        skip_dedup=True,
        skip_promote=True,
        skip_lint=True,
        skip_reindex=True,
        runtime_session_loader=lambda: "FLEET DIGEST v1",
        now=1000.0,
    )
    assert any("fleet snapshot recorded" in n for n in result.notes)
    rows = _fleet_rows(project.memory_db_path)
    assert len(rows) == 1
    assert rows[0][1] == "FLEET DIGEST v1"


def test_dream_cycle_replaces_prior_snapshot(tmp_path: Path):
    project = init_project(tmp_path / "p", name="p")
    SessionStore(project.memory_db_path).close()

    common = dict(
        skip_insights=True,
        skip_dedup=True,
        skip_promote=True,
        skip_lint=True,
        skip_reindex=True,
    )
    dream_cycle(project, runtime_session_loader=lambda: "v1", now=1000.0, **common)
    dream_cycle(project, runtime_session_loader=lambda: "v2", now=2000.0, **common)

    rows = _fleet_rows(project.memory_db_path)
    assert len(rows) == 1  # single living snapshot, not accreting
    assert rows[0][1] == "v2"


def test_dream_cycle_no_loader_writes_nothing(tmp_path: Path):
    project = init_project(tmp_path / "p", name="p")
    SessionStore(project.memory_db_path).close()
    dream_cycle(
        project,
        skip_insights=True,
        skip_dedup=True,
        skip_promote=True,
        skip_lint=True,
        skip_reindex=True,
        now=1000.0,
    )
    assert _fleet_rows(project.memory_db_path) == []


def test_dream_cycle_loader_returns_none_writes_nothing(tmp_path: Path):
    project = init_project(tmp_path / "p", name="p")
    SessionStore(project.memory_db_path).close()
    dream_cycle(
        project,
        skip_insights=True,
        skip_dedup=True,
        skip_promote=True,
        skip_lint=True,
        skip_reindex=True,
        runtime_session_loader=lambda: None,
        now=1000.0,
    )
    assert _fleet_rows(project.memory_db_path) == []
