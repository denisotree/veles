"""M125: `memory_save_insight` and `memory_save_rule` builtin tools.

These are SQL-direct writers used by the curator agent and the insight
extractor to land distilled output in M119 `insights` / `rules` tables.
M161: the insights row is canonical; a markdown view is rendered to
`.veles/memory/insights/` and backfilled into `file_path` when the
caller didn't supply one."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.context import current_project, reset_active_project, set_active_project
from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.core.tools.builtin.memory_save import (
    memory_save_insight,
    memory_save_rule,
    save_insight_row,
    save_rule_row,
)


@pytest.fixture(autouse=True)
def _clear_active_project():
    """Other test modules may leave the ContextVar pointing at a stale
    project. Reset before every test here so the "no active project"
    cases see a true None state."""
    token = set_active_project(None)
    yield
    try:
        reset_active_project(token)
    except Exception:
        pass


@pytest.fixture()
def project(tmp_path: Path):
    proj = init_project(tmp_path / "proj", name="proj")
    token = set_active_project(proj)
    yield proj
    reset_active_project(token)


# ---- insights ----


def test_save_insight_writes_row(project) -> None:
    result = memory_save_insight(
        title="Auth refactor decision",
        body="Use JWT cookies, not Authorization header — fewer CORS edge cases.",
        category="architecture",
        file_path="wiki/sessions/abc.md",
    )
    assert "saved insight" in result
    assert "#1" in result or "#2" in result  # exact id depends on seed rows

    store = SessionStore(project.memory_db_path)
    row = store._conn.execute(
        "SELECT title, body, category, file_path FROM insights WHERE category=?",
        ("architecture",),
    ).fetchone()
    store._conn.close()
    assert row is not None
    assert row["title"] == "Auth refactor decision"
    assert "JWT" in row["body"]
    assert row["category"] == "architecture"
    assert row["file_path"] == "wiki/sessions/abc.md"


def test_save_insight_no_file_path_renders_view(project) -> None:
    """M161: empty file_path → backfilled with the rendered memory view."""
    memory_save_insight(
        title="Empty path", body="b", category="curated-session"
    )
    store = SessionStore(project.memory_db_path)
    row = store._conn.execute(
        "SELECT id, file_path FROM insights WHERE title=?", ("Empty path",)
    ).fetchone()
    store._conn.close()
    assert row["file_path"] == f".veles/memory/insights/empty-path-{row['id']}.md"
    view = project.root / row["file_path"]
    assert view.is_file()
    assert "Empty path" in view.read_text(encoding="utf-8")


def test_save_insight_idempotent_runs(project) -> None:
    """Calling twice creates two rows — there's no dedupe key, so callers
    decide. Verify both land."""
    memory_save_insight(title="A", body="x", category="curated-session")
    memory_save_insight(title="A", body="y", category="curated-session")
    store = SessionStore(project.memory_db_path)
    count = store._conn.execute(
        "SELECT COUNT(*) AS n FROM insights WHERE title=?", ("A",)
    ).fetchone()["n"]
    store._conn.close()
    assert count == 2


def test_save_insight_no_active_project_errors_gracefully(tmp_path: Path) -> None:
    """When no project is active, the tool returns a friendly error
    string rather than crashing the agent."""
    # Don't use the project fixture — no active project here
    result = memory_save_insight(title="t", body="b", category="x")
    assert "<error" in result


# ---- rules ----


def test_save_rule_writes_row(project) -> None:
    result = memory_save_rule(
        kind="preference",
        body="User prefers terse responses; no trailing summaries.",
        source="session-abc123",
    )
    assert "saved rule" in result

    store = SessionStore(project.memory_db_path)
    row = store._conn.execute(
        "SELECT kind, body, source FROM rules WHERE source=?",
        ("session-abc123",),
    ).fetchone()
    store._conn.close()
    assert row is not None
    assert row["kind"] == "preference"
    assert "terse" in row["body"]
    assert row["source"] == "session-abc123"


def test_save_rule_rejects_invalid_kind(project) -> None:
    """Schema CHECK constraint allows only format/do/dont/preference.
    Tool rejects unknown kinds upfront with a helpful error."""
    del project  # ensure we still write nothing
    result = memory_save_rule(kind="bogus", body="x", source="x")
    assert "<error" in result
    assert "format" in result and "preference" in result  # lists valid kinds


def test_save_rule_each_kind_accepted(project) -> None:
    for kind in ("format", "do", "dont", "preference"):
        result = memory_save_rule(kind=kind, body=f"{kind} body", source="src")
        assert "saved rule" in result
    store = SessionStore(project.memory_db_path)
    count = store._conn.execute("SELECT COUNT(*) AS n FROM rules").fetchone()["n"]
    store._conn.close()
    assert count == 4


def test_save_rule_no_active_project_errors_gracefully(tmp_path: Path) -> None:
    result = memory_save_rule(kind="do", body="x", source="x")
    assert "<error" in result


# ---- programmatic helpers (used by insight_extractor mirror) ----


def test_save_insight_row_returns_id_on_success(project) -> None:
    rid = save_insight_row(
        title="t", body="b", category="x", file_path="wiki/x.md"
    )
    assert rid > 0


def test_save_insight_row_returns_zero_without_project(tmp_path: Path) -> None:
    rid = save_insight_row(title="t", body="b", category="x")
    assert rid == 0


def test_save_rule_row_returns_zero_on_invalid_kind(project) -> None:
    rid = save_rule_row(kind="invalid", body="b", source="s")
    assert rid == 0
