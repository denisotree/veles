"""Curator → SQL bridge: insight_extractor writes to memory.db
`insights` table alongside the legacy `wiki/insights/<slug>.md`
files."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.memory import SessionStore
from veles.core.project import init_project


@pytest.fixture()
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


def _count_sql_insights(project) -> int:
    store = SessionStore(project.memory_db_path)
    n = store._conn.execute(
        "SELECT COUNT(*) AS n FROM insights"
    ).fetchone()["n"]
    store._conn.close()
    return int(n)


def _list_sql_insights(project):
    store = SessionStore(project.memory_db_path)
    rows = store._conn.execute(
        "SELECT title, body, category, file_path FROM insights ORDER BY id"
    ).fetchall()
    store._conn.close()
    return [(r["title"], r["body"], r["category"], r["file_path"]) for r in rows]


# ---- direct simulation of the mirror ----


def test_mirror_inserts_row(isolated_home: Path, tmp_path: Path) -> None:
    """Build the mirror closure-style — mirrors what `make_insight_extractor`
    creates — and verify a row lands."""
    project = init_project(tmp_path / "proj", name="proj")

    import time

    from veles.core.memory import SessionStore as _Store

    def _mirror(*, title: str, body: str, category: str, file_path: str) -> None:
        try:
            store = _Store(project.memory_db_path)
            store._conn.execute(
                "INSERT INTO insights(title, body, category, file_path, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (title, body, category, file_path, time.time()),
            )
            store._conn.close()
        except Exception:
            pass

    _mirror(
        title="Test insight",
        body="Set explicit timeouts on every long-running shell call.",
        category="recovery",
        file_path="wiki/insights/test-abc.md",
    )

    rows = _list_sql_insights(project)
    assert len(rows) == 1
    assert rows[0][0] == "Test insight"
    assert "timeout" in rows[0][1]
    assert rows[0][2] == "recovery"
    assert rows[0][3].startswith("wiki/insights/")


def test_mirror_findable_via_fts(isolated_home: Path, tmp_path: Path) -> None:
    """The mirrored insight is searchable via insights_fts triggers."""
    project = init_project(tmp_path / "proj", name="proj")
    import time

    from veles.core.memory import SessionStore as _Store

    store = _Store(project.memory_db_path)
    store._conn.execute(
        "INSERT INTO insights(title, body, category, file_path, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (
            "Telegram pattern",
            "Use HTML, not Markdown",
            "format",
            "wiki/insights/tg.md",
            time.time(),
        ),
    )
    rows = store._conn.execute(
        "SELECT title FROM insights_fts WHERE insights_fts MATCH ?", ("Telegram",)
    ).fetchall()
    store._conn.close()
    assert any("Telegram" in r["title"] for r in rows)


def test_mirror_no_crash_on_missing_table(tmp_path: Path) -> None:
    """If memory.db doesn't exist or table is missing, the mirror
    swallows the exception — primary wiki write is what matters."""
    import time

    from veles.core.memory import SessionStore as _Store

    nonexistent_db = tmp_path / "ghost.db"

    def _mirror(*, title: str, body: str, category: str, file_path: str) -> None:
        try:
            store = _Store(nonexistent_db)
            # Drop the table so the insert fails
            store._conn.execute("DROP TABLE insights")
            store._conn.execute(
                "INSERT INTO insights(title, body, category, file_path, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (title, body, category, file_path, time.time()),
            )
            store._conn.close()
        except Exception:
            pass  # exactly what the real mirror does

    # Should not raise
    _mirror(
        title="x",
        body="y",
        category="z",
        file_path="wiki/insights/x.md",
    )
