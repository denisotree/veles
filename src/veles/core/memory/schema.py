"""The `memory.db` schema and its forward-only migrations.

`PRAGMA user_version` holds the schema version. `init_schema` creates what is
missing (every statement is `IF NOT EXISTS`) and runs each migration the file
has not had yet:

- v2: FTS5 index `turns_fts` over `turns.content` (external content, kept in
  sync by triggers) and a one-shot rebuild from existing rows;
- v3: the relational backbone — tools, skills, rules, insights with their
  telemetry tables and FTS shadows;
- v4–v8: columns added to `insights` (confidence, superseded_by,
  hidden_at/hidden_reason, origin/support_count, synced_at), with backfills.
"""

from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 8

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    id                 TEXT PRIMARY KEY,
    created_at         REAL NOT NULL,
    last_activity_at   REAL NOT NULL,
    title              TEXT,
    parent_session_id  TEXT REFERENCES sessions(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS turns (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    seq             INTEGER NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('system','user','assistant','tool')),
    content         TEXT,
    tool_calls_json TEXT,
    tool_call_id    TEXT,
    created_at      REAL NOT NULL,
    UNIQUE (session_id, seq),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_turns_session    ON turns(session_id, seq);
CREATE INDEX IF NOT EXISTS idx_sessions_activity ON sessions(last_activity_at DESC);
"""

# External-content FTS5 index over `turns.content`, linked by rowid (=turns.id)
# so the body is not duplicated; triggers keep it in lockstep with the table.
FTS_SCHEMA_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS turns_fts USING fts5(
    content,
    content='turns',
    content_rowid='id',
    tokenize = 'unicode61 remove_diacritics 1'
);

CREATE TRIGGER IF NOT EXISTS turns_ai AFTER INSERT ON turns BEGIN
    INSERT INTO turns_fts(rowid, content) VALUES (new.id, new.content);
END;

CREATE TRIGGER IF NOT EXISTS turns_ad AFTER DELETE ON turns BEGIN
    INSERT INTO turns_fts(turns_fts, rowid, content) VALUES('delete', old.id, old.content);
END;

CREATE TRIGGER IF NOT EXISTS turns_au AFTER UPDATE ON turns BEGIN
    INSERT INTO turns_fts(turns_fts, rowid, content) VALUES('delete', old.id, old.content);
    INSERT INTO turns_fts(rowid, content) VALUES (new.id, new.content);
END;
"""

# The relational backbone of project memory: tools, skills, rules, insights
# with telemetry tables. Embeddings are created on demand by `memory.vector`.
SCHEMA_V3_SQL = """
CREATE TABLE IF NOT EXISTS tools (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL UNIQUE,
    scope         TEXT NOT NULL CHECK (scope IN ('builtin','project','user')),
    origin        TEXT NOT NULL CHECK (origin IN ('builtin','agent-generated','manual')),
    base_tool_id  INTEGER REFERENCES tools(id) ON DELETE SET NULL,
    manifest_json TEXT,
    description   TEXT,
    created_at    REAL NOT NULL,
    updated_at    REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tools_scope_origin ON tools(scope, origin);
CREATE INDEX IF NOT EXISTS idx_tools_base ON tools(base_tool_id);

CREATE TABLE IF NOT EXISTS tool_uses (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_id      INTEGER NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
    session_id   TEXT REFERENCES sessions(id) ON DELETE SET NULL,
    turn_id      INTEGER REFERENCES turns(id) ON DELETE SET NULL,
    invoked_at   REAL NOT NULL,
    ok           INTEGER NOT NULL CHECK (ok IN (0,1)),
    latency_ms   INTEGER,
    error_kind   TEXT
);

CREATE INDEX IF NOT EXISTS idx_tool_uses_tool ON tool_uses(tool_id, invoked_at DESC);
CREATE INDEX IF NOT EXISTS idx_tool_uses_session ON tool_uses(session_id);

CREATE TABLE IF NOT EXISTS skills (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    scope           TEXT NOT NULL CHECK (scope IN ('builtin','project','user')),
    base_skill_id   INTEGER REFERENCES skills(id) ON DELETE SET NULL,
    frontmatter_json TEXT,
    description     TEXT,
    file_path       TEXT,
    created_at      REAL NOT NULL,
    updated_at      REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_skills_scope ON skills(scope);
CREATE INDEX IF NOT EXISTS idx_skills_base ON skills(base_skill_id);

CREATE TABLE IF NOT EXISTS skill_tool_refs (
    skill_id  INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    tool_id   INTEGER NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
    args_json TEXT,
    PRIMARY KEY (skill_id, tool_id)
);

CREATE TABLE IF NOT EXISTS skill_uses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id    INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    session_id  TEXT REFERENCES sessions(id) ON DELETE SET NULL,
    invoked_at  REAL NOT NULL,
    ok          INTEGER NOT NULL CHECK (ok IN (0,1)),
    latency_ms  INTEGER,
    error_kind  TEXT
);

CREATE INDEX IF NOT EXISTS idx_skill_uses_skill ON skill_uses(skill_id, invoked_at DESC);

CREATE TABLE IF NOT EXISTS rules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    kind            TEXT NOT NULL CHECK (kind IN ('format','do','dont','preference')),
    body            TEXT NOT NULL,
    source          TEXT,           -- 'explicit-feedback' | 'extracted'
    created_at      REAL NOT NULL,
    last_applied_at REAL,
    decay_score     REAL NOT NULL DEFAULT 1.0
);

CREATE INDEX IF NOT EXISTS idx_rules_kind ON rules(kind);
CREATE INDEX IF NOT EXISTS idx_rules_decay ON rules(decay_score DESC);

CREATE TABLE IF NOT EXISTS insights (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    title              TEXT NOT NULL,
    body               TEXT NOT NULL,
    category           TEXT,
    file_path          TEXT,
    created_at         REAL NOT NULL,
    last_referenced_at REAL,
    -- Provenance confidence in [0,1]. 1.0 = user-asserted / curated; lower =
    -- heuristically inferred. Recall prunes sub-floor rows before the prompt.
    confidence         REAL NOT NULL DEFAULT 1.0,
    -- The insight that replaced this one, or NULL while this row is current.
    -- See `eligibility.eligible_sql`. The row itself is never deleted.
    superseded_by      INTEGER REFERENCES insights(id) ON DELETE SET NULL,
    -- When this insight stopped being offered to recall, and why. Hiding is the
    -- ONLY way a fact leaves recall — nothing deletes from this table — so the
    -- pair makes the removal reversible (clear the columns) and explainable.
    -- `hidden_reason` vocabulary: merged-duplicate | superseded | user-retracted.
    hidden_at          REAL,
    hidden_reason      TEXT,
    -- Where the fact came from, kept separate from `confidence`: `stated` the
    -- user said it · `derived` the agent concluded it · `heuristic` a trigger
    -- guessed it. NULL = unknown (written before the column existed). Ranking
    -- deliberately ignores it, so existing rows are not silently re-ranked.
    origin             TEXT,
    -- How many observations back this fact. Dedup adds the support of every
    -- duplicate it collapses, so a repeatedly-observed fact carries its
    -- evidence instead of merely surviving.
    support_count      INTEGER NOT NULL DEFAULT 1,
    -- When this fact was last handed to the external memory engine, or NULL.
    -- Dual-write is best-effort (the local row is the source of truth), so the
    -- ones that did not make it have to be findable afterwards.
    synced_at          REAL
);

CREATE INDEX IF NOT EXISTS idx_insights_category ON insights(category);
CREATE INDEX IF NOT EXISTS idx_insights_recent ON insights(last_referenced_at DESC);

CREATE TABLE IF NOT EXISTS insight_refs (
    from_insight_id INTEGER NOT NULL REFERENCES insights(id) ON DELETE CASCADE,
    to_insight_id   INTEGER NOT NULL REFERENCES insights(id) ON DELETE CASCADE,
    PRIMARY KEY (from_insight_id, to_insight_id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS rules_fts USING fts5(
    body, content='rules', content_rowid='id',
    tokenize='unicode61 remove_diacritics 1'
);

CREATE TRIGGER IF NOT EXISTS rules_ai AFTER INSERT ON rules BEGIN
    INSERT INTO rules_fts(rowid, body) VALUES (new.id, new.body);
END;

CREATE TRIGGER IF NOT EXISTS rules_ad AFTER DELETE ON rules BEGIN
    INSERT INTO rules_fts(rules_fts, rowid, body) VALUES('delete', old.id, old.body);
END;

CREATE TRIGGER IF NOT EXISTS rules_au AFTER UPDATE ON rules BEGIN
    INSERT INTO rules_fts(rules_fts, rowid, body) VALUES('delete', old.id, old.body);
    INSERT INTO rules_fts(rowid, body) VALUES (new.id, new.body);
END;

CREATE VIRTUAL TABLE IF NOT EXISTS insights_fts USING fts5(
    title, body, content='insights', content_rowid='id',
    tokenize='unicode61 remove_diacritics 1'
);

CREATE TRIGGER IF NOT EXISTS insights_ai AFTER INSERT ON insights BEGIN
    INSERT INTO insights_fts(rowid, title, body) VALUES (new.id, new.title, new.body);
END;

CREATE TRIGGER IF NOT EXISTS insights_ad AFTER DELETE ON insights BEGIN
    INSERT INTO insights_fts(insights_fts, rowid, title, body)
        VALUES('delete', old.id, old.title, old.body);
END;

CREATE TRIGGER IF NOT EXISTS insights_au AFTER UPDATE ON insights BEGIN
    INSERT INTO insights_fts(insights_fts, rowid, title, body)
        VALUES('delete', old.id, old.title, old.body);
    INSERT INTO insights_fts(rowid, title, body) VALUES (new.id, new.title, new.body);
END;
"""


def init_schema(c: sqlite3.Connection) -> None:
    """Create the schema and run every migration this database has not had."""
    c.executescript(_SCHEMA_SQL)
    # The per-session model-override table was retired (model and provider are
    # fixed at daemon launch); drop the orphan so nothing can resurrect it.
    c.execute("DROP TABLE IF EXISTS session_model_overrides")
    current = c.execute("PRAGMA user_version").fetchone()[0]
    for version, migrate in enumerate(_MIGRATIONS, start=2):
        if current < version:
            migrate(c)
    if current < SCHEMA_VERSION:
        c.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def _add_column_if_missing(c: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    """`ALTER TABLE <table> ADD COLUMN <column> <ddl>` unless it already exists."""
    if column not in {r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()}:
        c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def _migrate_to_v2(c: sqlite3.Connection) -> None:
    """FTS5 over turns, then a rebuild from existing rows. FTS5's own 'rebuild'
    is the reliable backfill: an `INSERT … SELECT … LEFT JOIN turns_fts` silently
    indexes nothing, because the planner treats the empty FTS as the outer rowset."""
    c.executescript(FTS_SCHEMA_SQL)
    c.execute("INSERT INTO turns_fts(turns_fts) VALUES('rebuild')")


def _migrate_to_v3(c: sqlite3.Connection) -> None:
    """The relational backbone. Purely additive, so safe on any v2 database."""
    c.executescript(SCHEMA_V3_SQL)


def _migrate_to_v4(c: sqlite3.Connection) -> None:
    """`insights.confidence`; existing rows default to full confidence."""
    _add_column_if_missing(c, "insights", "confidence", "REAL NOT NULL DEFAULT 1.0")


def _migrate_to_v5(c: sqlite3.Connection) -> None:
    """`insights.superseded_by`, and the existing supersession links moved off
    `insight_refs` onto it. The only writer of those refs was dream dedup, so
    every existing ref *is* a supersession and the backfill is exact; the refs
    rows are then deleted. No insight row is removed."""
    _add_column_if_missing(
        c, "insights", "superseded_by", "INTEGER REFERENCES insights(id) ON DELETE SET NULL"
    )
    c.execute(
        "UPDATE insights SET superseded_by = ("
        "    SELECT to_insight_id FROM insight_refs"
        "     WHERE from_insight_id = insights.id LIMIT 1"
        ") WHERE superseded_by IS NULL"
        "  AND id IN (SELECT from_insight_id FROM insight_refs)"
    )
    c.execute("DELETE FROM insight_refs")


def _migrate_to_v6(c: sqlite3.Connection) -> None:
    """`insights.hidden_at` / `hidden_reason`. Recall eligibility moves onto
    `hidden_at`, so every already-superseded row is stamped (reason
    `merged-duplicate`, the only writer) or it would reappear in recall. The
    real moment of hiding was never recorded; `COALESCE(last_referenced_at,
    created_at)` — when the fact was last alive — approximates it better than
    the upgrade time would."""
    _add_column_if_missing(c, "insights", "hidden_at", "REAL")
    _add_column_if_missing(c, "insights", "hidden_reason", "TEXT")
    c.execute(
        "UPDATE insights"
        "   SET hidden_at = COALESCE(last_referenced_at, created_at),"
        "       hidden_reason = 'merged-duplicate'"
        " WHERE superseded_by IS NOT NULL AND hidden_at IS NULL"
    )


def _migrate_to_v7(c: sqlite3.Connection) -> None:
    """`insights.origin` / `support_count`. Origin is backfilled only where the
    category states it outright (the two insight-extractor triggers); every other
    row keeps NULL rather than a guess."""
    _add_column_if_missing(c, "insights", "origin", "TEXT")
    _add_column_if_missing(c, "insights", "support_count", "INTEGER NOT NULL DEFAULT 1")
    c.execute(
        "UPDATE insights SET origin = CASE category"
        "   WHEN 'remember-trigger' THEN 'stated'"
        "   WHEN 'recovery-trigger' THEN 'heuristic'"
        " END"
        " WHERE origin IS NULL AND category IN ('remember-trigger', 'recovery-trigger')"
    )


def _migrate_to_v8(c: sqlite3.Connection) -> None:
    """`insights.synced_at`; existing rows stay NULL — they genuinely have not
    been sent to an external engine, so a later resync offers them."""
    _add_column_if_missing(c, "insights", "synced_at", "REAL")


# Index 0 is the v1 → v2 step; `init_schema` runs every step past the file's version.
_MIGRATIONS = (
    _migrate_to_v2,
    _migrate_to_v3,
    _migrate_to_v4,
    _migrate_to_v5,
    _migrate_to_v6,
    _migrate_to_v7,
    _migrate_to_v8,
)
assert len(_MIGRATIONS) == SCHEMA_VERSION - 1
