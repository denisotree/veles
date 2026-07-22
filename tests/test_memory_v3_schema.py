"""M119: memory.db schema v3 — relational backbone for VISION §5.1.

We test the schema directly via `SessionStore` (the only public path to
the database). M119b will add sqlite-vec embeddings; that's a separate
test file once the extension is wired up.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.memory import _SCHEMA_VERSION, SessionStore


@pytest.fixture()
def store(tmp_path: Path) -> SessionStore:
    return SessionStore(tmp_path / "memory.db")


def _tables(store: SessionStore) -> set[str]:
    rows = store._conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','virtual table')"
    ).fetchall()
    return {r["name"] for r in rows}


def _cols(store: SessionStore, table: str) -> set[str]:
    return {r["name"] for r in store._conn.execute(f"PRAGMA table_info({table})").fetchall()}


# ---- schema presence ----


def test_v3_user_version_bumped(store: SessionStore) -> None:
    v = store._conn.execute("PRAGMA user_version").fetchone()[0]
    assert v == _SCHEMA_VERSION


def test_v3_tables_present(store: SessionStore) -> None:
    tables = _tables(store)
    expected = {
        "tools",
        "tool_uses",
        "skills",
        "skill_tool_refs",
        "skill_uses",
        "rules",
        "insights",
        "insight_refs",
        "rules_fts",
        "insights_fts",
    }
    missing = expected - tables
    assert not missing, missing


def test_tools_columns(store: SessionStore) -> None:
    cols = _cols(store, "tools")
    assert {
        "id",
        "name",
        "scope",
        "origin",
        "base_tool_id",
        "manifest_json",
        "description",
        "created_at",
        "updated_at",
    } <= cols


def test_skills_columns(store: SessionStore) -> None:
    cols = _cols(store, "skills")
    assert {
        "id",
        "name",
        "scope",
        "base_skill_id",
        "frontmatter_json",
        "description",
        "file_path",
        "created_at",
        "updated_at",
    } <= cols


# ---- inserts and constraints ----


def test_insert_tool_and_use(store: SessionStore) -> None:
    c = store._conn
    c.execute(
        "INSERT INTO tools(name, scope, origin, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        ("read_file", "builtin", "builtin", 1.0, 1.0),
    )
    tool_id = c.execute("SELECT id FROM tools WHERE name = ?", ("read_file",)).fetchone()["id"]
    c.execute(
        "INSERT INTO tool_uses(tool_id, invoked_at, ok, latency_ms) VALUES (?, ?, ?, ?)",
        (tool_id, 2.0, 1, 42),
    )
    use_count, success_count = c.execute(
        "SELECT COUNT(*) AS uc, SUM(ok) AS sc FROM tool_uses WHERE tool_id = ?",
        (tool_id,),
    ).fetchone()
    assert use_count == 1
    assert success_count == 1


def test_tool_scope_constraint(store: SessionStore) -> None:
    """`scope` is restricted to known values."""
    import sqlite3 as _sqlite3

    c = store._conn
    with pytest.raises(_sqlite3.IntegrityError):
        c.execute(
            "INSERT INTO tools(name, scope, origin, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("x", "bogus_scope", "builtin", 1.0, 1.0),
        )


def test_unique_tool_name(store: SessionStore) -> None:
    import sqlite3 as _sqlite3

    c = store._conn
    c.execute(
        "INSERT INTO tools(name, scope, origin, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        ("dup", "user", "manual", 1.0, 1.0),
    )
    with pytest.raises(_sqlite3.IntegrityError):
        c.execute(
            "INSERT INTO tools(name, scope, origin, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("dup", "user", "manual", 2.0, 2.0),
        )


def test_skill_inheritance_via_recursive_cte(store: SessionStore) -> None:
    """A parent → child chain resolves via the standard recursive CTE."""
    c = store._conn
    c.executemany(
        "INSERT INTO skills(name, scope, base_skill_id, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?)",
        [
            ("base", "builtin", None, 1.0, 1.0),
            ("mid", "user", 1, 1.0, 1.0),
            ("leaf", "project", 2, 1.0, 1.0),
        ],
    )
    rows = c.execute(
        """
        WITH RECURSIVE chain(id, base_skill_id, depth) AS (
            SELECT id, base_skill_id, 0 FROM skills WHERE name = ?
            UNION ALL
            SELECT s.id, s.base_skill_id, c.depth + 1
            FROM skills s JOIN chain c ON s.id = c.base_skill_id
        )
        SELECT depth, id FROM chain ORDER BY depth
        """,
        ("leaf",),
    ).fetchall()
    depths = [r["depth"] for r in rows]
    assert depths == [0, 1, 2]


def test_rules_fts_indexed_on_insert(store: SessionStore) -> None:
    """rules_fts is a content-linked FTS5 table — INSERT triggers
    populate it so MATCH queries find rules immediately."""
    c = store._conn
    c.execute(
        "INSERT INTO rules(kind, body, source, created_at) VALUES (?, ?, ?, ?)",
        (
            "dont",
            "always set explicit timeout on long-running shell calls",
            "explicit-feedback",
            1.0,
        ),
    )
    matches = c.execute(
        "SELECT body FROM rules_fts WHERE rules_fts MATCH ?", ("timeout",)
    ).fetchall()
    assert len(matches) == 1
    assert "timeout" in matches[0]["body"]


def test_insights_fts_searches_title_and_body(store: SessionStore) -> None:
    c = store._conn
    c.execute(
        "INSERT INTO insights(title, body, category, created_at) VALUES (?, ?, ?, ?)",
        ("Telegram pattern", "Use HTML, not Markdown", "format", 1.0),
    )
    rows = c.execute(
        "SELECT title FROM insights_fts WHERE insights_fts MATCH ?", ("Telegram",)
    ).fetchall()
    assert any("Telegram" in r["title"] for r in rows)


# ---- idempotency ----


def test_reopening_store_does_not_re_migrate(tmp_path: Path) -> None:
    """Closing and reopening the same db path leaves the schema at v3
    with no extra side effects (`_migrate_to_v3` is idempotent)."""
    db = tmp_path / "memory.db"
    store1 = SessionStore(db)
    v1 = store1._conn.execute("PRAGMA user_version").fetchone()[0]
    store1._conn.close()
    store2 = SessionStore(db)
    v2 = store2._conn.execute("PRAGMA user_version").fetchone()[0]
    assert v1 == v2 == _SCHEMA_VERSION
    # Tables are still here.
    tables = _tables(store2)
    assert {"tools", "skills", "rules", "insights"} <= tables


def test_legacy_v2_database_upgrades_to_v3(tmp_path: Path) -> None:
    """A database opened with `PRAGMA user_version = 2` (an older Veles
    install) gets the v3 tables added on next open, without losing v2
    state."""
    import sqlite3 as _sqlite3

    db = tmp_path / "memory.db"
    # Build a fresh v2-shaped database manually.
    conn = _sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY, created_at REAL NOT NULL,
            last_activity_at REAL NOT NULL, title TEXT,
            parent_session_id TEXT
        );
        CREATE TABLE IF NOT EXISTS turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL, seq INTEGER NOT NULL,
            role TEXT NOT NULL, content TEXT, tool_calls_json TEXT,
            tool_call_id TEXT, created_at REAL NOT NULL,
            UNIQUE(session_id, seq)
        );
        PRAGMA user_version = 2;
        """
    )
    conn.execute(
        "INSERT INTO sessions(id, created_at, last_activity_at) VALUES (?, ?, ?)",
        ("legacy-1", 1.0, 1.0),
    )
    conn.commit()
    conn.close()

    # Open through SessionStore — migration runs.
    store = SessionStore(db)
    v = store._conn.execute("PRAGMA user_version").fetchone()[0]
    assert v == _SCHEMA_VERSION
    tables = _tables(store)
    assert "tools" in tables
    # Legacy row survived.
    rows = store._conn.execute("SELECT id FROM sessions WHERE id = ?", ("legacy-1",)).fetchall()
    assert len(rows) == 1
