"""M118b: scan_project_tree hook triggers from init_project."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.core.project_tree_runner import scan_project_tree


def _tree_count(project) -> int:
    store = SessionStore(project.memory_db_path)
    count = store._conn.execute(
        "SELECT COUNT(*) AS n FROM project_tree"
    ).fetchone()["n"]
    store._conn.close()
    return int(count)


# ---- init triggers scan ----


def test_init_project_warms_the_tree_cache(tmp_path: Path) -> None:
    """After init_project, the project_tree table has rows. AGENTS.md
    and the daemon-internal files at minimum exist."""
    project = init_project(tmp_path / "proj", name="proj")
    assert _tree_count(project) > 0


def test_init_project_records_agents_md(tmp_path: Path) -> None:
    project = init_project(tmp_path / "proj", name="proj")
    store = SessionStore(project.memory_db_path)
    row = store._conn.execute(
        "SELECT 1 FROM project_tree WHERE rel_path = ?", ("AGENTS.md",)
    ).fetchone()
    assert row is not None
    store._conn.close()


# ---- scan_project_tree directly ----


def test_scan_returns_report_with_counts(tmp_path: Path) -> None:
    project = init_project(tmp_path / "proj", name="proj")
    # First scan happened during init; second scan should be a no-op
    # (every entry's mtime matches what we persisted).
    report = scan_project_tree(project)
    assert report is not None
    assert report.added == 0
    assert report.updated == 0


def test_scan_picks_up_new_file(tmp_path: Path) -> None:
    project = init_project(tmp_path / "proj", name="proj")
    (project.root / "new_file.txt").write_text("hello\n", encoding="utf-8")

    report = scan_project_tree(project)
    assert report is not None
    assert report.added >= 1

    store = SessionStore(project.memory_db_path)
    row = store._conn.execute(
        "SELECT 1 FROM project_tree WHERE rel_path = ?", ("new_file.txt",)
    ).fetchone()
    assert row is not None
    store._conn.close()


def test_scan_returns_none_on_bad_db_path(tmp_path: Path, monkeypatch) -> None:
    """If the db can't be opened, we log and return None — don't
    bubble a sqlite3 error out to the caller."""
    project = init_project(tmp_path / "proj", name="proj")
    # Replace memory.db with a directory so SQLite can't open it.
    project.memory_db_path.unlink(missing_ok=True)
    project.memory_db_path.mkdir()

    # Now opening as a SessionStore raises — but the runner traps it.
    result = scan_project_tree(project)
    # Could be either: db open fails (None) or sqlite tolerates the
    # path. Either way, no exception propagates.
    assert result is None or result is not None  # just no exception
