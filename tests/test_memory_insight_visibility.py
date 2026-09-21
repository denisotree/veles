"""M258/M260: supersession moves off `insight_refs`, and hiding gets a reason.

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


# ---- M260: visibility carries a reason, and nothing is deleted ----


def test_v6_hides_rows_that_were_already_superseded(tmp_path: Path) -> None:
    """Eligibility moved onto `hidden_at`, so a pre-M260 supersession has to be
    stamped during the migration — otherwise every duplicate dedup collapsed
    would walk back into recall."""
    db = tmp_path / "memory.db"
    canonical, dup = _make_v4_db(db)

    store = SessionStore(db)
    try:
        row = store._conn.execute(
            "SELECT hidden_at, hidden_reason, superseded_by FROM insights WHERE id = ?", (dup,)
        ).fetchone()
        assert row["hidden_at"] is not None
        assert row["hidden_reason"] == "merged-duplicate"
        assert row["superseded_by"] == canonical
        ids = [h.id for h in store.search_insights("redis ttl session", limit=5)]
        assert ids == [canonical]
    finally:
        store.close()


def test_hidden_insight_is_still_stored_and_unhideable(tmp_path: Path) -> None:
    """The invariant the whole design rests on: hiding removes a fact from
    recall, never from the database, so clearing the columns brings it back."""
    store = SessionStore(tmp_path / "memory.db")
    try:
        kept = _insert_insight(store._conn, "kept", "postgres vacuum runs nightly")
        hidden = _insert_insight(store._conn, "hidden", "postgres vacuum runs weekly")
        store._conn.execute(
            "UPDATE insights SET hidden_at = 1.0, hidden_reason = 'user-retracted' WHERE id = ?",
            (hidden,),
        )
        store._conn.commit()

        assert [h.id for h in store.search_insights("postgres vacuum", limit=5)] == [kept]
        # still on disk, with its reason
        row = store._conn.execute(
            "SELECT body, hidden_reason FROM insights WHERE id = ?", (hidden,)
        ).fetchone()
        assert row["body"] == "postgres vacuum runs weekly"
        assert row["hidden_reason"] == "user-retracted"

        store._conn.execute(
            "UPDATE insights SET hidden_at = NULL, hidden_reason = NULL WHERE id = ?", (hidden,)
        )
        store._conn.commit()
        ids = {h.id for h in store.search_insights("postgres vacuum", limit=5)}
        assert ids == {kept, hidden}
    finally:
        store.close()


def test_dedup_records_why_it_hid_the_duplicate(tmp_path: Path) -> None:
    from veles.core.dreaming import DreamResult, _step_insight_dedup
    from veles.core.project import init_project

    project = init_project(tmp_path / "p", name="p")
    conn = sqlite3.connect(str(project.memory_db_path))
    try:
        conn.execute(
            "INSERT INTO insights(title, body, category, created_at, last_referenced_at)"
            " VALUES ('a', 'bump nginx worker_connections concurrent sockets',"
            " 'curated-session', 100.0, 100.0)"
        )
        conn.execute(
            "INSERT INTO insights(title, body, category, created_at, last_referenced_at)"
            " VALUES ('b', 'increase nginx worker_connections concurrent sockets',"
            " 'curated-session', 200.0, 200.0)"
        )
        conn.commit()
    finally:
        conn.close()

    _step_insight_dedup(project, DreamResult(), dry_run=False)

    conn = sqlite3.connect(str(project.memory_db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, hidden_at, hidden_reason FROM insights WHERE hidden_at IS NOT NULL"
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 1
    assert rows[0]["hidden_reason"] == "merged-duplicate"
    assert rows[0]["hidden_at"] > 0


# ---- M261: provenance, kept separate from the ranking weight ----


def test_v7_backfills_origin_only_where_category_states_it(tmp_path: Path) -> None:
    """A guessed origin would defeat the column. Rows whose category names the
    trigger are backfilled; everything else stays NULL — unknown, and honest
    about it."""
    db = tmp_path / "memory.db"
    _make_v4_db(db)
    conn = sqlite3.connect(str(db))
    try:
        for title, category in (
            ("remembered", "remember-trigger"),
            ("recovered", "recovery-trigger"),
            ("curated", "curated-session"),
        ):
            conn.execute(
                "INSERT INTO insights(title, body, category, created_at)"
                " VALUES (?, 'body', ?, 1000.0)",
                (title, category),
            )
        conn.commit()
    finally:
        conn.close()

    store = SessionStore(db)
    try:
        origins = dict(
            store._conn.execute(
                "SELECT title, origin FROM insights WHERE category IS NOT 'test'"
            ).fetchall()
        )
    finally:
        store.close()
    assert origins["remembered"] == "stated"
    assert origins["recovered"] == "heuristic"
    assert origins["curated"] is None


def test_origin_does_not_change_ranking(tmp_path: Path) -> None:
    """M261 is read-only provenance: `confidence` still decides the weight, so
    adding the column re-ranks nothing. A heuristic row written with full
    confidence must rank exactly as it did before."""
    from veles.core.project import init_project
    from veles.core.tools.builtin.memory_save import save_insight_row

    project = init_project(tmp_path / "p", name="p")
    rid = save_insight_row(
        title="guessed",
        body="kafka retention is seven days",
        category="recovery-trigger",
        project=project,
        confidence=1.0,
        origin="heuristic",
    )
    store = SessionStore(project.memory_db_path)
    try:
        row = store._conn.execute(
            "SELECT origin, support_count FROM insights WHERE id = ?", (rid,)
        ).fetchone()
        hit = store.search_insights("kafka retention", limit=1)[0]
    finally:
        store.close()
    assert row["origin"] == "heuristic"
    assert row["support_count"] == 1
    assert hit.confidence == 1.0  # untouched by origin


def test_dedup_gives_the_survivor_the_merged_support(tmp_path: Path) -> None:
    from veles.core.dreaming import DreamResult, _step_insight_dedup
    from veles.core.project import init_project

    project = init_project(tmp_path / "p", name="p")
    conn = sqlite3.connect(str(project.memory_db_path))
    try:
        for title, body, ts in (
            ("a", "bump nginx worker_connections concurrent sockets", 100.0),
            ("b", "increase nginx worker_connections concurrent sockets", 200.0),
            ("c", "raise nginx worker_connections for concurrent sockets", 300.0),
        ):
            conn.execute(
                "INSERT INTO insights(title, body, category, created_at, last_referenced_at)"
                " VALUES (?, ?, 'curated-session', ?, ?)",
                (title, body, ts, ts),
            )
        conn.commit()
    finally:
        conn.close()

    _step_insight_dedup(project, DreamResult(), dry_run=False)

    conn = sqlite3.connect(str(project.memory_db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = {
            r["title"]: (r["support_count"], r["hidden_reason"])
            for r in conn.execute(
                "SELECT title, support_count, hidden_reason FROM insights"
            ).fetchall()
        }
    finally:
        conn.close()
    # `c` is the most recently referenced → canonical, and inherits a + b.
    assert rows["c"] == (3, None)
    assert rows["a"][1] == "merged-duplicate"
    assert rows["b"][1] == "merged-duplicate"
