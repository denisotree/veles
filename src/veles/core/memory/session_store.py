"""`SessionStore` — the SQLite store behind a project's `memory.db`.

Conversation history (one row per turn, grouped by session with an ordinal
`seq`; tool calls in `tool_calls_json`, `tool_call_id` linking a tool result to
its call), plus the recall reads over insights and rules. `db_path` is a real
path (usually `<project>/.veles/memory.db`) or `":memory:"` in tests. The schema
lives in `memory/schema.py`.
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
from veles.core.memory.schema import FTS_SCHEMA_SQL, SCHEMA_V3_SQL, init_schema
from veles.core.provider import Message, ToolCall
from veles.core.text import ellipsize

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SessionInfo:
    id: str
    created_at: float
    last_activity_at: float
    title: str | None
    turn_count: int


@dataclass(slots=True, frozen=True)
class DigestRule:
    """One behavioural rule for the system-prompt digest.
    `kind` ∈ format/do/dont/preference."""

    kind: str
    body: str


@dataclass(slots=True, frozen=True)
class InsightHit:
    """One recall match against the `insights` table. `rank` is BM25 for full-text
    hits and cosine distance for vector hits — lower is more relevant either way.
    `ts` is `coalesce(last_referenced_at, created_at)`, the recency signal for
    reranking (a recall hit refreshes it)."""

    id: int
    title: str
    body: str
    rank: float
    ts: float
    confidence: float = 1.0  # provenance confidence in [0,1]


@dataclass(slots=True, frozen=True)
class TurnHit:
    """One FTS5 match against `turns.content`.

    `rank` is SQLite's BM25 score — lower is more relevant. Tests should only
    assert relative ordering: BM25 weights vary with corpus statistics.
    """

    session_id: str
    seq: int
    role: str
    content: str
    created_at: float
    rank: float


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
    It is a function rather than raw SQL at each writer because the three
    columns move together: a row hidden without a reason, or a `superseded_by`
    written without `hidden_at`, leaves the old fact competing with its
    replacement. `reason` vocabulary: merged-duplicate | superseded |
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

_SESSION_COLUMNS = (
    "SELECT s.id, s.created_at, s.last_activity_at, s.title,"
    " (SELECT COUNT(*) FROM turns WHERE session_id=s.id) AS turn_count"
    " FROM sessions s"
)


def _session_title(text: str) -> str:
    """First non-blank line of `text`, whitespace collapsed, cut to one list row."""
    for raw in text.splitlines():
        line = " ".join(raw.split())
        if line:
            return ellipsize(line, _SESSION_TITLE_MAX)
    return ""


def _row_to_session_info(row: sqlite3.Row) -> SessionInfo:
    return SessionInfo(
        id=row["id"],
        created_at=row["created_at"],
        last_activity_at=row["last_activity_at"],
        title=row["title"],
        turn_count=row["turn_count"],
    )


def _insight_hit(row: sqlite3.Row, rank: float) -> InsightHit:
    return InsightHit(
        id=int(row["id"]),
        title=row["title"] or "",
        body=row["body"] or "",
        rank=rank,
        ts=float(row["ts"]),
        confidence=float(row["confidence"]),
    )


class SessionStore:
    def __init__(self, db_path: Path | str) -> None:
        self._conn = open_sqlite(db_path)
        init_schema(self._conn)

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

    def session_exists(self, session_id: str) -> bool:
        """True iff a row with this id is in `sessions`.

        Callers resuming a session from an external source (channel session
        map, daemon HTTP body) check this before `append_turn`, whose first
        insert would otherwise trip the foreign key."""
        row = self._conn.execute(
            "SELECT 1 FROM sessions WHERE id = ? LIMIT 1",
            (session_id,),
        ).fetchone()
        return row is not None

    def top_rules(self, limit: int = 12) -> list[DigestRule]:
        """The highest-ranked behavioural rules for the house-rules digest.

        Ranked by `decay_score DESC`, then most-recently-applied, then newest
        (NULL `last_applied_at` sorts last under DESC). Best-effort: `[]` if the
        table is missing or the query errors, so prompt assembly never raises."""
        try:
            rows = self._conn.execute(
                "SELECT kind, body FROM rules"
                " ORDER BY decay_score DESC, last_applied_at DESC, created_at DESC"
                " LIMIT ?",
                (limit,),
            ).fetchall()
        except sqlite3.Error:
            return []
        return [DigestRule(kind=r["kind"], body=r["body"]) for r in rows]

    def append_turn(self, session_id: str, message: Message) -> int:
        # Sanitize on the write boundary so future loads of this row are
        # already clean; `load_messages` sanitizes again for older rows.
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
            # Title a session from its first user message. Done here rather than
            # at `create_session` because a daemon or channel opens the session
            # before its first message exists, and every path that records a
            # conversation comes through this method. `title IS NULL` keeps the
            # first message's title and never overwrites a set one.
            if message.role == "user" and content:
                title = _session_title(content)
                if title:
                    self._conn.execute(
                        "UPDATE sessions SET title=? WHERE id=? AND title IS NULL",
                        (title, session_id),
                    )
        return int(next_seq)

    def load_messages(self, session_id: str) -> list[Message]:
        # Sanitize on the read boundary too — rows written before a redaction
        # rule existed still need their leaks redacted before the agent sees them.
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

    def _select_sessions(self, tail: str, params: tuple[Any, ...]) -> list[SessionInfo]:
        rows = self._conn.execute(f"{_SESSION_COLUMNS} {tail}", params).fetchall()
        return [_row_to_session_info(r) for r in rows]

    def list_sessions(self, *, limit: int = 20) -> list[SessionInfo]:
        return self._select_sessions("ORDER BY s.last_activity_at DESC LIMIT ?", (limit,))

    def list_sessions_since(self, since: float, *, limit: int = 50) -> list[SessionInfo]:
        """Sessions with last_activity_at > `since`, oldest-first — the curator
        walks them in order so its cursor advances monotonically."""
        return self._select_sessions(
            "WHERE s.last_activity_at > ? ORDER BY s.last_activity_at ASC LIMIT ?",
            (since, limit),
        )

    def get_session(self, session_id: str) -> SessionInfo | None:
        found = self._select_sessions("WHERE id=?", (session_id,))
        return found[0] if found else None

    def search_turns(
        self,
        query: str,
        *,
        limit: int = 10,
        role_filter: tuple[str, ...] | None = ("user", "assistant"),
        since: float | None = None,
    ) -> list[TurnHit]:
        """FTS5 search over `turns.content`.

        - Empty / whitespace-only `query` → `[]`.
        - `role_filter=None` includes every role; the default keeps user and
          assistant turns, since tool payloads and system prompts are noise.
        - `since` (UNIX time) keeps only turns created at or after it.

        Most relevant first (BM25). On FTS unavailability (corrupt index, SQLite
        without FTS5) returns `[]` rather than raising — recall must degrade.
        """
        escaped = escape_query(query)
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
        try:
            rows = self._conn.execute(" ".join(sql_parts), params).fetchall()
        except sqlite3.OperationalError as exc:
            # Degrade to [] (recall must never raise) but log: a corrupt/missing
            # FTS index otherwise looks exactly like "no memory".
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
        """FTS5 BM25 search over the `insights` table, most relevant first,
        hidden (superseded or retracted) rows excluded. Degrades to `[]` on an
        empty query or FTS unavailability — recall must never raise here."""
        escaped = escape_query(query)
        if not escaped:
            return []
        try:
            rows = self._conn.execute(
                "SELECT i.id, i.title, i.body, insights_fts.rank AS rank,"
                " COALESCE(i.last_referenced_at, i.created_at) AS ts, i.confidence AS confidence"
                " FROM insights_fts JOIN insights i ON insights_fts.rowid = i.id"
                " WHERE insights_fts MATCH ?"
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
        return [_insight_hit(r, float(r["rank"])) for r in rows]

    def fts_ok(self) -> bool:
        """Probe the FTS shadow indexes. False when a MATCH raises (dropped or
        corrupt index) — the exact condition under which recall would silently
        return nothing. Repair with `rebuild_fts`."""
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
        """Recreate any missing FTS shadow tables/triggers and rebuild each index
        from its base table. Idempotent — the repair behind `veles doctor --fix`."""
        self._conn.executescript(FTS_SCHEMA_SQL)
        self._conn.executescript(SCHEMA_V3_SQL)
        for tbl in ("turns_fts", "insights_fts", "rules_fts"):
            try:
                self._conn.execute(f"INSERT INTO {tbl}({tbl}) VALUES('rebuild')")
            except sqlite3.OperationalError as exc:
                logger.warning("rebuild_fts: could not rebuild %s (%s)", tbl, exc)
        self._conn.commit()

    def knn_insights(self, query_vec: list[float], *, limit: int = 5) -> list[InsightHit]:
        """Nearest-neighbour insights by embedding cosine distance, nearest first,
        hiding exactly what `search_insights` hides. Degrades to `[]` on error."""
        from veles.core.memory.vector import knn

        try:
            # Over-fetch: some neighbours may be hidden and filtered out.
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
        for n in neighbours:  # keep knn's nearest-first order
            r = by_id.get(n.ref_id)
            if r is None:
                continue
            out.append(_insight_hit(r, float(n.distance)))
            if len(out) >= limit:
                break
        return out

    def touch_insights(self, ids: list[int], at: float) -> None:
        """Stamp `last_referenced_at` for recalled insights (the recency signal).
        Best-effort, single statement, never raises."""
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
        """Delete raw `turns` from old sessions the curator has finished with;
        returns the number of rows removed.

        **Raw material is disposable, what was learned from it is not.** `turns`
        are the transcript — the bulkiest thing in `memory.db` and the only part
        that grows without bound. Insights, rules and their embeddings are what
        the transcript was read *for*, and are never touched here.

        **`curated_before` is load-bearing.** It is `CuratorState.last_curated_at`,
        so only sessions the curator has already swept are eligible; pruning on
        age alone would delete a transcript before anything was extracted from it.

        **Session rows stay** (id, timestamps, title), so `veles sessions list`
        keeps the history; only the bodies go, and `veles sessions search` can no
        longer find text older than the window. The `turns_fts` delete triggers
        keep the index consistent.
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
