"""Persistent session memory — SQLite-backed conversation history.

Schema is idempotent (CREATE TABLE IF NOT EXISTS). One row per turn, grouped by
session_id with auto-incremented `seq`. Tool calls live in `tool_calls_json` for
assistant messages; `tool_call_id` links a `tool` message back to its call.

`db_path` is **required** (since M3): callers must pass either a real Path
(usually `<project>/.veles/memory.db`) or the special string `":memory:"` for
unit tests. WAL mode is enabled for real paths; SQLite refuses WAL on `:memory:`
so we skip it there.

`PRAGMA user_version` marks the schema version. v1 = M1 baseline
(sessions + turns + indices). v2 = M58: external-content FTS5 index
`turns_fts(content)` over `turns(content)` keyed on `rowid=turns.id`,
kept in sync via three triggers (insert/delete/update). Migration is
forward-only: on open we read user_version, run the v1→v2 patch if
needed (CREATE VIRTUAL TABLE + triggers + one-shot rebuild from
existing rows), bump to 2.
"""

from __future__ import annotations

import json
import logging
import secrets
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from veles.core.fts import escape_query
from veles.core.io_utils import open_sqlite
from veles.core.memory.eligibility import eligible_sql
from veles.core.provider import Message, ToolCall

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SessionInfo:
    id: str
    created_at: float
    last_activity_at: float
    title: str | None
    turn_count: int


@dataclass(slots=True, frozen=True)
class RuleRow:
    """One behavioural rule (M139). `kind` ∈ format/do/dont/preference."""

    kind: str
    body: str


@dataclass(slots=True, frozen=True)
class InsightHit:
    """One FTS5 match against the `insights` table (M140). `rank` is BM25 —
    lower is more relevant, like `TurnHit.rank`. `ts` (M141) is
    `coalesce(last_referenced_at, created_at)` — the recency signal for
    reranking (a recall hit refreshes it, mem0-style)."""

    id: int
    title: str
    body: str
    rank: float
    ts: float
    confidence: float = 1.0  # M218: provenance confidence in [0,1]


@dataclass(slots=True, frozen=True)
class TurnHit:
    """One FTS5 match against `turns.content` (M58).

    `rank` is SQLite's BM25 score — lower is more relevant. Tests should
    only assert relative ordering, never an absolute number, because
    BM25 weights vary with corpus statistics.
    """

    session_id: str
    seq: int
    role: str
    content: str
    created_at: float
    rank: float


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
# M127: the `session_model_overrides` table (per-session model swap from
# Telegram `/model`) was removed — model/provider are now fixed at daemon
# launch from config. Old DBs keep an orphan table that nothing reads.

# M58: external-content FTS5 index over `turns.content`. The FTS table is
# linked to `turns` by rowid (=turns.id) so the row body is not duplicated;
# triggers keep the FTS rows in lockstep with INSERT/DELETE/UPDATE on turns.
_FTS_SCHEMA_SQL = """
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

# M119: schema v3 adds the relational backbone for VISION §5.1's
# project memory: tools, skills, rules, insights with telemetry tables.
# sqlite-vec embeddings table is deferred to M119b (loadable extension
# needs runtime install with a numpy fallback) — recursive-CTE queries
# for skill/tool inheritance work on the relational tables alone.
_SCHEMA_V3_SQL = """
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
    -- M218: provenance confidence in [0,1]. 1.0 = user-asserted / curated;
    -- lower = heuristically inferred (e.g. a tool-error recovery guess).
    -- Recall prunes sub-floor rows before they reach the prompt.
    confidence         REAL NOT NULL DEFAULT 1.0,
    -- M258: the insight that replaced this one, or NULL while this row is
    -- the current one. Supersession used to be encoded as an `insight_refs`
    -- row, which made it indistinguishable from any other relation; see
    -- `eligibility.eligible_sql`. The row itself is never deleted.
    superseded_by      INTEGER REFERENCES insights(id) ON DELETE SET NULL,
    -- M260: when this insight stopped being offered to recall, and why.
    -- Hiding is the ONLY way a fact leaves recall — nothing deletes from this
    -- table — so the pair is what makes the removal reversible (clear the
    -- columns) and explainable (`/insights` prints the reason).
    -- `hidden_reason` vocabulary: merged-duplicate | superseded | user-retracted.
    hidden_at          REAL,
    hidden_reason      TEXT,
    -- M261: where the fact came from, kept separate from `confidence`.
    -- `stated` the user said it · `derived` the agent concluded it ·
    -- `heuristic` a trigger guessed it. NULL = written before M261, unknown.
    -- Read-only provenance for now: ranking deliberately ignores it, because
    -- folding it into `confidence` would silently re-rank every existing row.
    origin             TEXT,
    -- How many observations back this fact. Dedup adds the support of every
    -- duplicate it collapses, so a repeatedly-observed fact carries its
    -- evidence instead of merely surviving.
    support_count      INTEGER NOT NULL DEFAULT 1,
    -- M265: when this fact was last handed to the external memory engine, or
    -- NULL when it has not been. Dual-write is best-effort by design -- the
    -- local row is the source of truth and a network failure must not lose a
    -- fact or fail a turn -- so the ones that did not make it have to be
    -- findable afterwards, or "best-effort" quietly means "sometimes never".
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

_SCHEMA_VERSION = 8


def hide_insight(
    conn: sqlite3.Connection,
    insight_id: int,
    *,
    reason: str,
    superseded_by: int | None = None,
    now: float | None = None,
) -> bool:
    """Take one insight out of recall, recording why. Returns False when the
    row was already hidden (the call is then a no-op, not an error).

    This is the ONLY supported way a fact leaves recall — there is no delete.
    It exists as a function rather than raw SQL at each writer because the
    three columns have to move together: a row hidden without a reason is
    exactly the state M260 set out to remove, and a `superseded_by` written
    without `hidden_at` leaves the old fact competing with the one that
    replaced it. `reason` vocabulary: merged-duplicate | superseded |
    user-retracted.
    """
    cur = conn.execute(
        "UPDATE insights SET hidden_at = ?, hidden_reason = ?,"
        "   superseded_by = COALESCE(?, superseded_by)"
        " WHERE id = ? AND hidden_at IS NULL",
        (time.time() if now is None else now, reason, superseded_by, insight_id),
    )
    return cur.rowcount > 0


def _make_session_id() -> str:
    return f"{int(time.time()):010d}-{secrets.token_hex(4)}"


_SESSION_TITLE_MAX = 60


def _session_title(text: str) -> str:
    """First non-blank line of `text`, whitespace collapsed, cut to one list row."""
    for line in text.splitlines():
        line = " ".join(line.split())
        if line:
            if len(line) > _SESSION_TITLE_MAX:
                return line[: _SESSION_TITLE_MAX - 1].rstrip() + "…"
            return line
    return ""


class SessionStore:
    def __init__(self, db_path: Path | str) -> None:
        self._conn = open_sqlite(db_path)
        self._init_schema()

    def _init_schema(self) -> None:
        c = self._conn
        c.executescript(_SCHEMA_SQL)
        # M127-removal: the per-session model-override table was retired in
        # M127 (model/provider fixed at daemon launch). Nothing reads it
        # anymore, but old DBs still carry the orphan table (+ a possibly
        # stale Telegram `/model` row). Drop it on open so it can't be
        # resurrected by any future code path. No-op on DBs that never had it.
        c.execute("DROP TABLE IF EXISTS session_model_overrides")
        current = c.execute("PRAGMA user_version").fetchone()[0]
        if current < 2:
            self._migrate_to_v2(c)
        if current < 3:
            self._migrate_to_v3(c)
        if current < 4:
            self._migrate_to_v4(c)
        if current < 5:
            self._migrate_to_v5(c)
        if current < 6:
            self._migrate_to_v6(c)
        if current < 7:
            self._migrate_to_v7(c)
        if current < 8:
            self._migrate_to_v8(c)
        if current < _SCHEMA_VERSION:
            c.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")

    def _migrate_to_v2(self, c: sqlite3.Connection) -> None:
        """v1 → v2: install FTS5 virtual table + triggers, backfill existing rows.

        Idempotent: CREATE statements are guarded with IF NOT EXISTS so
        a freshly-created database (already at v2 logically) just no-ops.
        Backfill walks every existing turn and inserts into turns_fts so
        databases opened from the M1 era pick up search coverage on the
        first M58 open.
        """
        c.executescript(_FTS_SCHEMA_SQL)
        # Backfill: rebuild the external-content FTS index from scratch
        # off the live `turns` table. FTS5 ships a built-in 'rebuild'
        # command for exactly this — atomic, idempotent, and the only
        # path that survives the LEFT-JOIN-during-INSERT anti-pattern
        # (an explicit `SELECT … LEFT JOIN turns_fts …` query in the
        # INSERT body silently fails to index because SQLite's planner
        # treats the empty FTS as the outer rowset).
        c.execute("INSERT INTO turns_fts(turns_fts) VALUES('rebuild')")

    def _migrate_to_v3(self, c: sqlite3.Connection) -> None:
        """v2 → v3: add the M119 relational backbone (tools / tool_uses /
        skills / skill_tool_refs / skill_uses / rules / insights /
        insight_refs + their FTS shadows). Pure additive — no existing
        tables are touched, so the migration is safe on any v2 database.
        Idempotent: every statement uses IF NOT EXISTS.

        sqlite-vec embeddings table is deferred (M119b) because loading
        the extension can fail on platforms without prebuilt wheels;
        keeping that out of the unconditional migration path means the
        schema bump never blocks startup on a stock Python.
        """
        c.executescript(_SCHEMA_V3_SQL)

    def _migrate_to_v4(self, c: sqlite3.Connection) -> None:
        """v3 → v4: add `insights.confidence` (M218). Additive; existing rows
        default to 1.0 (full confidence), so recall behaviour is unchanged
        until a writer starts assigning lower values."""
        cols = {r[1] for r in c.execute("PRAGMA table_info(insights)").fetchall()}
        if "confidence" not in cols:
            c.execute("ALTER TABLE insights ADD COLUMN confidence REAL NOT NULL DEFAULT 1.0")

    def _migrate_to_v5(self, c: sqlite3.Connection) -> None:
        """v4 → v5: add `insights.superseded_by` (M258) and move the existing
        supersession links off `insight_refs` onto it.

        Until now `insight_refs` carried both meanings — "A relates to B" and
        "A was superseded by B" — and recall hid every row appearing as a
        `from_insight_id`. The only writer is the M142 dream dedup, so every
        existing ref *is* a supersession and the backfill is exact; the refs
        rows are then deleted, leaving the table for the relations it is
        documented to hold. No insight row is removed: superseded rows stay
        readable and can be un-superseded by clearing the column.
        """
        cols = {r[1] for r in c.execute("PRAGMA table_info(insights)").fetchall()}
        if "superseded_by" not in cols:
            c.execute(
                "ALTER TABLE insights ADD COLUMN superseded_by INTEGER"
                " REFERENCES insights(id) ON DELETE SET NULL"
            )
        c.execute(
            "UPDATE insights SET superseded_by = ("
            "    SELECT to_insight_id FROM insight_refs"
            "     WHERE from_insight_id = insights.id LIMIT 1"
            ") WHERE superseded_by IS NULL"
            "  AND id IN (SELECT from_insight_id FROM insight_refs)"
        )
        c.execute("DELETE FROM insight_refs")

    def _migrate_to_v6(self, c: sqlite3.Connection) -> None:
        """v5 → v6: add `insights.hidden_at` / `hidden_reason` (M260).

        Recall eligibility moves onto `hidden_at`, so every row already
        superseded has to be stamped or it would reappear in recall — which
        would resurrect the duplicates dedup collapsed. The only writer of
        supersession is the M142 dream dedup, so the reason for existing rows
        is exactly `merged-duplicate`.

        The true moment of hiding was never recorded, so it is approximated by
        `COALESCE(last_referenced_at, created_at)` — when the fact was last
        alive — rather than by "now". `hidden_at` is the only visibility
        signal there is, and stamping every historical dedup with the upgrade
        time would tell any later "what did the agent stop using recently?"
        question that all of it happened at once.

        The UPDATE fires the `insights_au` FTS trigger once per affected row.
        It is one-shot and bounded by the number of already-superseded rows,
        which is why it is left as a plain statement.
        """
        cols = {r[1] for r in c.execute("PRAGMA table_info(insights)").fetchall()}
        if "hidden_at" not in cols:
            c.execute("ALTER TABLE insights ADD COLUMN hidden_at REAL")
        if "hidden_reason" not in cols:
            c.execute("ALTER TABLE insights ADD COLUMN hidden_reason TEXT")
        c.execute(
            "UPDATE insights"
            "   SET hidden_at = COALESCE(last_referenced_at, created_at),"
            "       hidden_reason = 'merged-duplicate'"
            " WHERE superseded_by IS NOT NULL AND hidden_at IS NULL"
        )

    def _migrate_to_v7(self, c: sqlite3.Connection) -> None:
        """v6 → v7: add `insights.origin` / `support_count` (M261).

        Origin is backfilled only where the existing `category` states it
        outright — the two insight-extractor triggers. Everything else keeps
        NULL rather than a guess: the column exists to say where a fact came
        from, and inventing that for old rows would defeat it. Nothing reads
        either column yet; ranking stays on `confidence` alone.
        """
        cols = {r[1] for r in c.execute("PRAGMA table_info(insights)").fetchall()}
        if "origin" not in cols:
            c.execute("ALTER TABLE insights ADD COLUMN origin TEXT")
        if "support_count" not in cols:
            c.execute("ALTER TABLE insights ADD COLUMN support_count INTEGER NOT NULL DEFAULT 1")
        c.execute(
            "UPDATE insights SET origin = CASE category"
            "   WHEN 'remember-trigger' THEN 'stated'"
            "   WHEN 'recovery-trigger' THEN 'heuristic'"
            " END"
            " WHERE origin IS NULL AND category IN ('remember-trigger', 'recovery-trigger')"
        )

    def _migrate_to_v8(self, c: sqlite3.Connection) -> None:
        """v7 → v8: add `insights.synced_at` (M265).

        Existing rows stay NULL, which is accurate rather than convenient: they
        predate the external engine and genuinely have not been sent. The
        resync step will offer them, which is the correct behaviour for a
        project that turns dual-write on later.
        """
        cols = {r[1] for r in c.execute("PRAGMA table_info(insights)").fetchall()}
        if "synced_at" not in cols:
            c.execute("ALTER TABLE insights ADD COLUMN synced_at REAL")

    def create_session(
        self, *, parent_session_id: str | None = None, title: str | None = None
    ) -> str:
        sid = _make_session_id()
        now = time.time()
        with self._tx():
            self._conn.execute(
                "INSERT INTO sessions"
                " (id, created_at, last_activity_at, title, parent_session_id)"
                " VALUES (?,?,?,?,?)",
                (sid, now, now, title, parent_session_id),
            )
        return sid

    # M127: `get_model_override` / `upsert_model_override` /
    # `load_all_model_overrides` / `latest_override_session_id` were
    # removed — per-session model overrides no longer exist (model and
    # provider are fixed at daemon launch from config). See the daemon's
    # `build_state` / `_handle_patch_session`.

    def session_exists(self, session_id: str) -> bool:
        """True iff a row with this id is in `sessions`.

        Callers that resume a session from an external source (channel
        session map, daemon HTTP body) need to verify the id is still
        valid before handing it to `append_turn`, otherwise the FK
        constraint trips on the first insert. The lookup is a cheap
        primary-key probe."""
        row = self._conn.execute(
            "SELECT 1 FROM sessions WHERE id = ? LIMIT 1",
            (session_id,),
        ).fetchone()
        return row is not None

    def top_rules(self, limit: int = 12) -> list[RuleRow]:
        """M139: the highest-ranked behavioural rules for the house-rules digest.

        Ranked by `decay_score DESC`, then most-recently-applied, then newest.
        SQLite sorts NULLs last under `DESC`, so unapplied rules (NULL
        `last_applied_at`) naturally fall below applied ones at equal decay.
        Best-effort: returns `[]` if the table is missing or the query errors,
        so prompt assembly never raises on a degraded DB."""
        try:
            rows = self._conn.execute(
                "SELECT kind, body FROM rules"
                " ORDER BY decay_score DESC, last_applied_at DESC, created_at DESC"
                " LIMIT ?",
                (limit,),
            ).fetchall()
        except sqlite3.Error:
            return []
        return [RuleRow(kind=r["kind"], body=r["body"]) for r in rows]

    def append_turn(self, session_id: str, message: Message) -> int:
        # Sanitize on the write boundary so future loads of this row are
        # already clean. Combined with the read-boundary sanitize in
        # `load_messages`, sessions are safe regardless of when the row
        # was inserted (pre- or post-rule-update).
        from veles.core.sanitize import sanitize

        now = time.time()
        content = sanitize(message.content) if message.content else message.content
        tool_calls_json = (
            json.dumps(
                [
                    {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                    for tc in message.tool_calls
                ]
            )
            if message.tool_calls
            else None
        )
        with self._tx():
            next_seq = self._conn.execute(
                "SELECT COALESCE(MAX(seq)+1, 0) AS next FROM turns WHERE session_id=?",
                (session_id,),
            ).fetchone()["next"]
            self._conn.execute(
                "INSERT INTO turns"
                " (session_id, seq, role, content, tool_calls_json, tool_call_id, created_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (
                    session_id,
                    next_seq,
                    message.role,
                    content,
                    tool_calls_json,
                    message.tool_call_id,
                    now,
                ),
            )
            self._conn.execute(
                "UPDATE sessions SET last_activity_at=? WHERE id=?",
                (now, session_id),
            )
            # Title a session from its first user message. The column existed,
            # the session picker, `veles sessions list` and `/resume` all show
            # it, and nothing ever wrote it — every session in every project was
            # "(untitled)" (0 of 9 in two real projects, 2026-09-22). Done here
            # rather than at `create_session` because a daemon or channel opens
            # the session before its first message exists; every path that
            # records a conversation comes through this method. `title IS NULL`
            # keeps the first message's title and never overwrites a set one.
            if message.role == "user" and content:
                title = _session_title(content)
                if title:
                    self._conn.execute(
                        "UPDATE sessions SET title=? WHERE id=? AND title IS NULL",
                        (title, session_id),
                    )
        return int(next_seq)

    def load_messages(self, session_id: str) -> list[Message]:
        # Sanitize on the read boundary too — rows written before the
        # sanitize module existed (or before a rule was added) still
        # need their leaks redacted before the agent sees them.
        from veles.core.sanitize import sanitize

        rows = self._conn.execute(
            "SELECT role, content, tool_calls_json, tool_call_id"
            " FROM turns WHERE session_id=? ORDER BY seq ASC",
            (session_id,),
        ).fetchall()
        out: list[Message] = []
        for row in rows:
            tool_calls: list[ToolCall] = []
            if row["tool_calls_json"]:
                for raw in json.loads(row["tool_calls_json"]):
                    tool_calls.append(
                        ToolCall(id=raw["id"], name=raw["name"], arguments=raw["arguments"])
                    )
            raw_content = row["content"]
            out.append(
                Message(
                    role=row["role"],
                    content=sanitize(raw_content) if raw_content else raw_content,
                    tool_calls=tool_calls,
                    tool_call_id=row["tool_call_id"],
                )
            )
        return out

    def list_sessions(self, *, limit: int = 20) -> list[SessionInfo]:
        rows = self._conn.execute(
            "SELECT s.id, s.created_at, s.last_activity_at, s.title,"
            " (SELECT COUNT(*) FROM turns WHERE session_id=s.id) AS turn_count"
            " FROM sessions s"
            " ORDER BY s.last_activity_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [_row_to_session_info(r) for r in rows]

    def list_sessions_since(self, since: float, *, limit: int = 50) -> list[SessionInfo]:
        """Return sessions with last_activity_at > `since`, oldest-first.

        Used by the curator to walk newly-active sessions in chronological
        order so its cursor advances monotonically.
        """
        rows = self._conn.execute(
            "SELECT s.id, s.created_at, s.last_activity_at, s.title,"
            " (SELECT COUNT(*) FROM turns WHERE session_id=s.id) AS turn_count"
            " FROM sessions s WHERE s.last_activity_at > ?"
            " ORDER BY s.last_activity_at ASC LIMIT ?",
            (since, limit),
        ).fetchall()
        return [_row_to_session_info(r) for r in rows]

    def get_session(self, session_id: str) -> SessionInfo | None:
        row = self._conn.execute(
            "SELECT s.id, s.created_at, s.last_activity_at, s.title,"
            " (SELECT COUNT(*) FROM turns WHERE session_id=s.id) AS turn_count"
            " FROM sessions s WHERE id=?",
            (session_id,),
        ).fetchone()
        return _row_to_session_info(row) if row else None

    def search_turns(
        self,
        query: str,
        *,
        limit: int = 10,
        role_filter: tuple[str, ...] | None = ("user", "assistant"),
        since: float | None = None,
    ) -> list[TurnHit]:
        """FTS5 search over `turns.content`.

        Resolution order:
        - Empty / whitespace-only `query` → `[]`.
        - `role_filter=None` includes every role (user/assistant/tool/system);
          default `("user", "assistant")` matches the common case where tool
          payloads + system prompts are noise rather than signal.
        - `since` is a UNIX timestamp; only turns with `created_at >= since`
          come back. `None` disables the cutoff.

        Returns `TurnHit` objects ordered by FTS5 BM25 rank ascending
        (most relevant first). On FTS unavailability (corrupt index,
        SQLite without FTS5) returns `[]` rather than raising — recall
        in production must degrade silently to wiki-only.
        """
        escaped = _fts_escape_query(query)
        if not escaped:
            return []
        sql_parts = [
            "SELECT t.session_id, t.seq, t.role, t.content, t.created_at, turns_fts.rank AS rank",
            "FROM turns_fts JOIN turns t ON turns_fts.rowid = t.id",
            "WHERE turns_fts MATCH ?",
        ]
        params: list[Any] = [escaped]
        if role_filter:
            placeholders = ",".join("?" * len(role_filter))
            sql_parts.append(f"AND t.role IN ({placeholders})")
            params.extend(role_filter)
        if since is not None:
            sql_parts.append("AND t.created_at >= ?")
            params.append(since)
        sql_parts.append("ORDER BY rank LIMIT ?")
        params.append(limit)
        sql = " ".join(sql_parts)
        try:
            rows = self._conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as exc:
            # M193: don't go silent. A corrupt/missing FTS index looks like
            # "no memory" otherwise. Degrade to [] (recall must never raise)
            # but log so `veles doctor` / the user can repair it.
            logger.warning(
                "search_turns: FTS unavailable (%s); recall degraded — run `veles doctor --fix`",
                exc,
            )
            return []
        return [
            TurnHit(
                session_id=row["session_id"],
                seq=int(row["seq"]),
                role=row["role"],
                content=row["content"] or "",
                created_at=float(row["created_at"]),
                rank=float(row["rank"]),
            )
            for row in rows
        ]

    def search_insights(self, query: str, *, limit: int = 5) -> list[InsightHit]:
        """M140: FTS5 BM25 search over the `insights` table.

        Returns `InsightHit`s ordered most-relevant-first. Degrades to `[]` on
        an empty query or FTS unavailability — recall must never raise here."""
        escaped = _fts_escape_query(query)
        if not escaped:
            return []
        try:
            rows = self._conn.execute(
                "SELECT i.id, i.title, i.body, insights_fts.rank AS rank,"
                " COALESCE(i.last_referenced_at, i.created_at) AS ts, i.confidence AS confidence"
                " FROM insights_fts JOIN insights i ON insights_fts.rowid = i.id"
                " WHERE insights_fts MATCH ?"
                # M142: skip insights superseded by dream dedup (kept on disk
                # for audit, but the canonical survivor is what recall surfaces).
                f" AND {eligible_sql('i')}"
                " ORDER BY rank LIMIT ?",
                (escaped, limit),
            ).fetchall()
        except sqlite3.OperationalError as exc:
            logger.warning(
                "search_insights: FTS unavailable (%s); recall degraded — run `veles doctor --fix`",
                exc,
            )
            return []
        return [
            InsightHit(
                id=int(r["id"]),
                title=r["title"] or "",
                body=r["body"] or "",
                rank=float(r["rank"]),
                ts=float(r["ts"]),
                confidence=float(r["confidence"]),
            )
            for r in rows
        ]

    def fts_ok(self) -> bool:
        """M193: probe the FTS shadow indexes. Returns False when a MATCH raises
        (dropped/corrupt index) — the exact condition under which recall would
        silently return nothing. Repair with `rebuild_fts`."""
        probe = '"__healthprobe__"'
        try:
            self._conn.execute(
                "SELECT rowid FROM turns_fts WHERE turns_fts MATCH ? LIMIT 1", (probe,)
            ).fetchall()
            self._conn.execute(
                "SELECT rowid FROM insights_fts WHERE insights_fts MATCH ? LIMIT 1", (probe,)
            ).fetchall()
        except sqlite3.OperationalError:
            return False
        return True

    def rebuild_fts(self) -> None:
        """M193: recreate any missing FTS shadow tables/triggers and rebuild each
        index from its external-content base table. Idempotent — the repair
        behind `veles doctor --fix`."""
        self._conn.executescript(_FTS_SCHEMA_SQL)
        self._conn.executescript(_SCHEMA_V3_SQL)
        for tbl in ("turns_fts", "insights_fts", "rules_fts"):
            try:
                self._conn.execute(f"INSERT INTO {tbl}({tbl}) VALUES('rebuild')")
            except sqlite3.OperationalError as exc:
                logger.warning("rebuild_fts: could not rebuild %s (%s)", tbl, exc)
        self._conn.commit()

    def knn_insights(self, query_vec: list[float], *, limit: int = 5) -> list[InsightHit]:
        """M192: nearest-neighbour insights by embedding cosine distance.

        Returns `InsightHit`s (rank = cosine distance, lower is nearer) ordered
        nearest-first, excluding superseded rows — vector recall must hide
        exactly what `search_insights` hides. Degrades to `[]` on any error."""
        from veles.core.memory.vector import knn

        try:
            # Over-fetch: some neighbours may be superseded and filtered out.
            neighbours = knn(self._conn, query_vec, ref_kind="insight", limit=limit * 3)
        except sqlite3.OperationalError:
            return []
        if not neighbours:
            return []
        ids = [h.ref_id for h in neighbours]
        placeholders = ",".join("?" * len(ids))
        rows = self._conn.execute(
            "SELECT id, title, body, COALESCE(last_referenced_at, created_at) AS ts, confidence"
            f" FROM insights WHERE id IN ({placeholders})"
            f" AND {eligible_sql()}",
            ids,
        ).fetchall()
        by_id = {int(r["id"]): r for r in rows}
        out: list[InsightHit] = []
        for n in neighbours:  # preserve nearest-first order from knn
            r = by_id.get(n.ref_id)
            if r is None:
                continue
            out.append(
                InsightHit(
                    id=int(r["id"]),
                    title=r["title"] or "",
                    body=r["body"] or "",
                    rank=float(n.distance),
                    ts=float(r["ts"]),
                    confidence=float(r["confidence"]),
                )
            )
            if len(out) >= limit:
                break
        return out

    def touch_insights(self, ids: list[int], at: float) -> None:
        """M140: stamp `last_referenced_at` for recalled insights (decay/aging).

        Best-effort, single statement, no raise — the first writer of this
        column in the codebase."""
        if not ids:
            return
        placeholders = ",".join("?" * len(ids))
        try:
            self._conn.execute(
                f"UPDATE insights SET last_referenced_at = ? WHERE id IN ({placeholders})",
                [at, *ids],
            )
            self._conn.commit()
        except sqlite3.Error:
            return

    def delete_session(self, session_id: str) -> bool:
        with self._tx():
            cur = self._conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        return cur.rowcount > 0

    def prune_turns(self, *, older_than: float, curated_before: float) -> int:
        """Delete raw `turns` from old sessions that the curator has finished
        with. Returns the number of rows removed (M257).

        **The retention model, decided 2026-09-18: raw material is disposable,
        what was learned from it is not.** `turns` are the transcript — the
        bulkiest thing in `memory.db` and the only part that grows without
        bound. `insights`, `rules` and their embeddings are what the transcript
        was read *for*, and are never touched here.

        **`curated_before` is the load-bearing argument, not a refinement.**
        It is `CuratorState.last_curated_at`, so only sessions the curator has
        already swept are eligible. Pruning on age alone would delete a
        transcript before anything had been extracted from it — losing the raw
        material *and* never producing the insight, which is worse than
        unbounded growth. A session the curator has not reached yet survives
        regardless of age.

        **Session rows stay.** They are metadata (id, timestamps, title) and
        cost almost nothing, so `veles sessions list` keeps showing the history;
        only the bodies go. The visible consequence is that
        `veles sessions search` — which searches `turns_fts` — can no longer
        find text older than the retention window. That is the trade being
        made, and the `turns_fts` delete triggers keep the index consistent
        rather than leaving it pointing at rows that are gone.
        """
        cutoff = min(older_than, curated_before)
        with self._tx():
            cur = self._conn.execute(
                "DELETE FROM turns WHERE session_id IN ("
                " SELECT id FROM sessions WHERE last_activity_at < ?)",
                (cutoff,),
            )
        return int(cur.rowcount or 0)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> SessionStore:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    @contextmanager
    def _tx(self):
        try:
            self._conn.execute("BEGIN")
            yield
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise


# M230: the FTS5 MATCH expression builder lives in `core/fts.py` so the optional
# wiki engine can share it without importing the memory subsystem. Re-exported
# under the historical private name — call sites and tests below use it directly.
_fts_escape_query = escape_query


def _row_to_session_info(row: sqlite3.Row) -> SessionInfo:
    return SessionInfo(
        id=row["id"],
        created_at=row["created_at"],
        last_activity_at=row["last_activity_at"],
        title=row["title"],
        turn_count=row["turn_count"],
    )
