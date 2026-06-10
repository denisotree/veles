"""M121d: post-turn curator triggers skill suggestion surfacing."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.cli._curator import _maybe_surface_skill_suggestions
from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.core.skill_suggester import SKILL_SUGGESTION_CATEGORY
from veles.core.tools.persistence import record_use, upsert_tool
from veles.core.tools.registry import ToolEntry


def _entry(name: str) -> ToolEntry:
    return ToolEntry(
        name=name,
        description=f"tool {name}",
        parameter_schema={"type": "object", "properties": {}, "required": []},
        handler=lambda **_kw: "",
        is_async=False,
    )


def _seed_session(conn, sid: str, sequence: list[str], base_time: float = 100.0) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO sessions(id, created_at, last_activity_at) VALUES (?, ?, ?)",
        (sid, base_time, base_time + len(sequence)),
    )
    for i, name in enumerate(sequence):
        record_use(
            conn,
            tool_name=name,
            ok=True,
            latency_ms=10,
            session_id=sid,
            now=base_time + i,
        )


@pytest.fixture()
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


# ---- happy path ----


def test_hook_surfaces_repeated_pattern(
    isolated_home: Path, tmp_path: Path
) -> None:
    """A 3x-repeated tool sequence becomes an insight row after the
    hook fires."""
    project = init_project(tmp_path / "proj", name="proj")
    store = SessionStore(project.memory_db_path)
    for name in ("wiki_search", "wiki_read_page"):
        upsert_tool(store._conn, _entry(name))
    seq = ["wiki_search", "wiki_read_page"]
    for i, sid in enumerate(["s1", "s2", "s3"]):
        _seed_session(store._conn, sid, seq, base_time=100.0 + i)
    store._conn.close()

    _maybe_surface_skill_suggestions(project)

    store2 = SessionStore(project.memory_db_path)
    row = store2._conn.execute(
        "SELECT title FROM insights WHERE category = ?",
        (SKILL_SUGGESTION_CATEGORY,),
    ).fetchone()
    assert row is not None
    assert "wiki_search" in row["title"]


def test_hook_no_patterns_no_writes(
    isolated_home: Path, tmp_path: Path
) -> None:
    """Empty tool_uses table → no insights written, no error."""
    project = init_project(tmp_path / "proj", name="proj")
    _maybe_surface_skill_suggestions(project)
    store = SessionStore(project.memory_db_path)
    count = store._conn.execute(
        "SELECT COUNT(*) AS n FROM insights WHERE category = ?",
        (SKILL_SUGGESTION_CATEGORY,),
    ).fetchone()["n"]
    assert count == 0


def test_hook_idempotent(isolated_home: Path, tmp_path: Path) -> None:
    """Two hook calls on the same data produce one insight, not two."""
    project = init_project(tmp_path / "proj", name="proj")
    store = SessionStore(project.memory_db_path)
    for name in ("wiki_search", "wiki_read_page"):
        upsert_tool(store._conn, _entry(name))
    for i, sid in enumerate(["s1", "s2", "s3"]):
        _seed_session(store._conn, sid, ["wiki_search", "wiki_read_page"], base_time=100.0 + i)
    store._conn.close()

    _maybe_surface_skill_suggestions(project)
    _maybe_surface_skill_suggestions(project)

    store2 = SessionStore(project.memory_db_path)
    count = store2._conn.execute(
        "SELECT COUNT(*) AS n FROM insights WHERE category = ?",
        (SKILL_SUGGESTION_CATEGORY,),
    ).fetchone()["n"]
    assert count == 1


# ---- error handling ----


def test_hook_silent_when_db_missing(tmp_path: Path) -> None:
    """If the memory.db can't be opened, the hook logs and returns —
    never raises into the curator caller."""
    from veles.core.project import Project

    fake_project = Project(
        root=tmp_path / "ghost",
        name="ghost",
        created_at=0.0,
    )
    # No init — memory.db doesn't exist, parent dir doesn't exist
    _maybe_surface_skill_suggestions(fake_project)  # should not raise
