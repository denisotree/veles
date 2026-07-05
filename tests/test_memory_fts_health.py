"""M193 — memory must not go silent.

Recall used to swallow `sqlite3.OperationalError` and return `[]`, so a corrupt
FTS index looked exactly like "no memory" — silent amnesia. These tests pin the
health probe + repair and the log-don't-swallow behaviour.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from veles.core.memory import SessionStore


def _seed_turn(store: SessionStore, content: str, *, session_id: str = "s1", seq: int = 0) -> None:
    now = time.time()
    store._conn.execute(
        "INSERT OR IGNORE INTO sessions(id, created_at, last_activity_at) VALUES(?, ?, ?)",
        (session_id, now, now),
    )
    store._conn.execute(
        "INSERT INTO turns(session_id, seq, role, content, created_at) VALUES(?, ?, ?, ?, ?)",
        (session_id, seq, "user", content, now),
    )
    store._conn.commit()


def test_fts_ok_true_on_healthy_store(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "m.db")
    try:
        assert store.fts_ok() is True
    finally:
        store.close()


def test_fts_ok_false_when_index_dropped(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "m.db")
    try:
        store._conn.execute("DROP TABLE turns_fts")
        store._conn.commit()
        assert store.fts_ok() is False
    finally:
        store.close()


def test_rebuild_fts_restores_search(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "m.db")
    try:
        _seed_turn(store, "kubernetes rollout strategy")
        store._conn.execute("DROP TABLE turns_fts")
        store._conn.commit()
        assert store.fts_ok() is False

        store.rebuild_fts()

        assert store.fts_ok() is True
        hits = store.search_turns("kubernetes")
        assert any("kubernetes" in h.content for h in hits)
    finally:
        store.close()


def test_search_turns_logs_instead_of_silently_swallowing(tmp_path: Path, caplog) -> None:
    store = SessionStore(tmp_path / "m.db")
    try:
        store._conn.execute("DROP TABLE turns_fts")
        store._conn.commit()
        with caplog.at_level(logging.WARNING):
            result = store.search_turns("anything")
        assert result == []  # still degrades to empty — recall never raises
        assert any("fts" in r.message.lower() for r in caplog.records)
    finally:
        store.close()


def _break_fts(project) -> None:
    store = SessionStore(project.memory_db_path)
    try:
        store._conn.execute("DROP TABLE turns_fts")
        store._conn.commit()
    finally:
        store.close()


def test_doctor_reports_broken_fts_as_error(tmp_path: Path) -> None:
    from veles.core.doctor import run_all
    from veles.core.project import init_project

    project = init_project(tmp_path, name="t")
    _break_fts(project)

    report = run_all(project)
    fts = next(r for r in report.results if r.name == "memory_fts")
    assert fts.status == "error"
    assert fts.fix_hint  # tells the user how to repair


def test_doctor_healthy_fts_is_ok(tmp_path: Path) -> None:
    from veles.core.doctor import run_all
    from veles.core.project import init_project

    project = init_project(tmp_path, name="t")
    report = run_all(project)
    fts = next(r for r in report.results if r.name == "memory_fts")
    assert fts.status == "ok"


def test_repair_memory_fts_rebuilds_index(tmp_path: Path) -> None:
    from veles.core.doctor import repair_memory_fts
    from veles.core.project import init_project

    project = init_project(tmp_path, name="t")
    _break_fts(project)

    assert repair_memory_fts(project) is True

    store = SessionStore(project.memory_db_path)
    try:
        assert store.fts_ok() is True
    finally:
        store.close()
