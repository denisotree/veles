"""M169 — memory_query: read-only SQL read-back over memory.db."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.context import reset_active_project, set_active_project
from veles.core.project import init_project
from veles.core.tools.builtin.memory_query import memory_query
from veles.core.tools.builtin.memory_save import memory_save_insight


@pytest.fixture()
def project(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    p = init_project(tmp_path / "proj", name="proj")
    token = set_active_project(p)
    yield p
    reset_active_project(token)


def test_reads_back_saved_insight(project):
    memory_save_insight("Prefer terse output", "User likes short answers", "preference")
    out = memory_query("SELECT title, category FROM insights")
    assert "Prefer terse output" in out
    assert "preference" in out
    assert "| title | category |" in out  # markdown header


def test_select_only_rejects_writes(project):
    for bad in (
        "DELETE FROM insights",
        "UPDATE insights SET title = 'x'",
        "INSERT INTO insights (title) VALUES ('x')",
        "DROP TABLE insights",
    ):
        out = memory_query(bad)
        assert "only read-only SELECT" in out


def test_query_only_blocks_write_disguised_in_cte(project):
    # Starts with WITH (allowed prefix) but attempts a write — PRAGMA
    # query_only must reject it at the engine level.
    out = memory_query("WITH x AS (SELECT 1) DELETE FROM insights")
    # Either the prefix guard or query_only stops it; nothing is deleted.
    assert out.startswith("<error")


def test_empty_query_errors(project):
    assert "empty query" in memory_query("   ")


def test_no_rows(project):
    assert memory_query("SELECT * FROM insights WHERE title = 'nope'") == "(no rows)"


def test_sqlite_master_discovery(project):
    out = memory_query("SELECT name FROM sqlite_master WHERE type='table' LIMIT 100")
    assert "insights" in out  # agent can discover its own schema


def test_truncation(project):
    for i in range(5):
        memory_save_insight(f"insight {i}", "body", "insight")
    out = memory_query("SELECT title FROM insights", max_rows=2)
    assert "truncated to 2 rows" in out
