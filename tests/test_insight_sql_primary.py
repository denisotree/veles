"""M161 — insights are SQL-primary: `save_insight_row` is the canonical
writer (recall/aging/dedup all read the row); the markdown under
`.veles/memory/insights/` is a rendered, regenerable view."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.memory import SessionStore
from veles.core.project import Project, init_project
from veles.core.tools.builtin.memory_save import save_insight_row


@pytest.fixture()
def project(tmp_path: Path) -> Project:
    return init_project(tmp_path / "proj", name="proj")


def _list_rows(project: Project):
    store = SessionStore(project.memory_db_path)
    rows = store._conn.execute(
        "SELECT id, title, body, category, file_path FROM insights ORDER BY id"
    ).fetchall()
    store._conn.close()
    return rows


def test_row_is_canonical_and_view_rendered(project: Project) -> None:
    rid = save_insight_row(
        title="Test insight",
        body="Set explicit timeouts on every long-running shell call.",
        category="recovery",
        project=project,
    )
    assert rid > 0
    rows = _list_rows(project)
    assert len(rows) == 1
    assert rows[0]["title"] == "Test insight"
    assert rows[0]["file_path"] == f".veles/memory/insights/test-insight-{rid}.md"
    view = project.root / rows[0]["file_path"]
    assert view.is_file()
    body = view.read_text(encoding="utf-8")
    assert "Test insight" in body
    assert "timeouts" in body


def test_explicit_file_path_is_kept_and_no_view_rendered(project: Project) -> None:
    """A caller-supplied file_path (e.g. the curator pointing at its wiki
    session page) wins; no memory view is rendered on top of it."""
    rid = save_insight_row(
        title="Curated",
        body="b",
        category="curated-session",
        file_path="wiki/sessions/abc.md",
        project=project,
    )
    assert rid > 0
    rows = _list_rows(project)
    assert rows[0]["file_path"] == "wiki/sessions/abc.md"
    assert not (project.memory_dir / "insights").exists() or not list(
        (project.memory_dir / "insights").glob("curated-*.md")
    )


def test_row_findable_via_fts(project: Project) -> None:
    save_insight_row(
        title="Telegram pattern",
        body="Use HTML, not Markdown",
        category="format",
        project=project,
    )
    store = SessionStore(project.memory_db_path)
    rows = store._conn.execute(
        "SELECT title FROM insights_fts WHERE insights_fts MATCH ?", ("Telegram",)
    ).fetchall()
    store._conn.close()
    assert any("Telegram" in r["title"] for r in rows)


def test_sql_failure_returns_zero_and_renders_nothing(project: Project) -> None:
    """SQL write is required: when it fails, no orphaned markdown view
    appears (an unsearchable file recall can't see would be rot)."""
    store = SessionStore(project.memory_db_path)
    store._conn.execute("DROP TABLE insights")
    store._conn.commit()
    store._conn.close()

    rid = save_insight_row(title="x", body="y", category="z", project=project)
    assert rid == 0
    insights_dir = project.memory_dir / "insights"
    assert not insights_dir.exists() or not list(insights_dir.iterdir())


def test_no_project_returns_zero(tmp_path: Path) -> None:
    from veles.core.context import reset_active_project, set_active_project

    token = set_active_project(None)
    try:
        assert save_insight_row(title="t", body="b", category="c") == 0
    finally:
        reset_active_project(token)
