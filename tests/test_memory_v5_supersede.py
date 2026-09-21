"""M258: supersession moves from `insight_refs` onto `insights.superseded_by`.

The migration has to be exact rather than best-effort: the M142 dream dedup was
the only writer of `insight_refs`, so every pre-v5 ref row *is* a supersession
and must survive the move. A row that silently stopped being hidden would put a
duplicate back into recall; a row that stayed hidden without a marker would be
unexplainable.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from veles.core.memory import (
    _FTS_SCHEMA_SQL,
    _SCHEMA_SQL,
    _SCHEMA_V3_SQL,
    _SCHEMA_VERSION,
    SessionStore,
)

# The v4 `insights` table is the current one minus the M258 column. Deriving it
# by removal (rather than pasting a frozen copy of the old DDL) keeps the
# fixture honest about everything else in the schema; the assert below fails
# loudly if the column definition is ever reworded.
_V5_COLUMN = (
    ",\n"
    "    -- M258: the insight that replaced this one, or NULL while this row is\n"
    "    -- the current one. Supersession used to be encoded as an `insight_refs`\n"
    "    -- row, which made it indistinguishable from any other relation; see\n"
    "    -- `eligibility.eligible_sql`. The row itself is never deleted.\n"
    "    superseded_by      INTEGER REFERENCES insights(id) ON DELETE SET NULL"
)


def _insert_insight(conn: sqlite3.Connection, title: str, body: str) -> int:
    cur = conn.execute(
        "INSERT INTO insights(title, body, category, file_path, created_at)"
        " VALUES (?, ?, 'test', NULL, 1000.0)",
        (title, body),
    )
    return int(cur.lastrowid or 0)


def _make_v4_db(path: Path) -> tuple[int, int]:
    """Build a v4-shaped database holding one dedup supersession."""
    assert _V5_COLUMN in _SCHEMA_V3_SQL, "M258 column definition moved — update this fixture"
    v4_sql = _SCHEMA_V3_SQL.replace(_V5_COLUMN, "")

    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(_SCHEMA_SQL)
        conn.executescript(_FTS_SCHEMA_SQL)
        conn.executescript(v4_sql)
        canonical = _insert_insight(conn, "canonical", "redis ttl 300 session keys")
        dup = _insert_insight(conn, "duplicate", "redis ttl 300 session keys")
        conn.execute(
            "INSERT INTO insight_refs(from_insight_id, to_insight_id) VALUES (?, ?)",
            (dup, canonical),
        )
        conn.execute("PRAGMA user_version = 4")
        conn.commit()
    finally:
        conn.close()
    return canonical, dup


def test_v5_migrates_refs_to_superseded_by(tmp_path: Path) -> None:
    db = tmp_path / "memory.db"
    canonical, dup = _make_v4_db(db)

    store = SessionStore(db)
    try:
        assert store._conn.execute("PRAGMA user_version").fetchone()[0] == _SCHEMA_VERSION
        rows = dict(store._conn.execute("SELECT id, superseded_by FROM insights").fetchall())
        assert rows[dup] == canonical
        assert rows[canonical] is None
        # The refs table keeps its documented meaning, so the migrated rows
        # must not stay behind and double as relations.
        assert store._conn.execute("SELECT COUNT(*) FROM insight_refs").fetchone()[0] == 0
        ids = [h.id for h in store.search_insights("redis ttl session", limit=5)]
        assert canonical in ids
        assert dup not in ids
    finally:
        store.close()


def test_v5_migration_is_idempotent(tmp_path: Path) -> None:
    """Reopening an already-migrated database must not resurrect or re-point
    anything — `_init_schema` runs on every open."""
    db = tmp_path / "memory.db"
    canonical, dup = _make_v4_db(db)

    SessionStore(db).close()
    store = SessionStore(db)
    try:
        rows = dict(store._conn.execute("SELECT id, superseded_by FROM insights").fetchall())
        assert rows[dup] == canonical
        assert rows[canonical] is None
    finally:
        store.close()


def test_fresh_db_has_superseded_by(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "memory.db")
    try:
        cols = {r["name"] for r in store._conn.execute("PRAGMA table_info(insights)").fetchall()}
        assert "superseded_by" in cols
    finally:
        store.close()
