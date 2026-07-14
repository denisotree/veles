"""TasksStore (M166) — SQLite-backed personal tasks + reminders.

Shares the project's `memory.db` (one DB per project keeps backup/export
simple). One `tasks` table, created on first open via CREATE TABLE IF NOT
EXISTS (additive — no user_version bump, so it coexists with the memory and
jobs schemas).

A task is a user-facing todo with an OPTIONAL reminder: when `due_at` passes
and a `deliver_to` is set, the daemon's `ReminderRunner` pushes the title to
that channel exactly once (idempotent via `reminded_at`). This is distinct
from `jobs` (scheduled prompt *executions*) — a task is "remind me about X at
time T", not "run this prompt on a schedule".

Snooze = reschedule (`due_at` bumped, `reminded_at` cleared); done closes it.
Methods are intentionally small CRUD + a `due_reminders` query; the sweep loop
lives in `ReminderRunner`, not here.

M214 (proactive delivery): two columns extend the model.
- `source` (`'user'|'dream'`): a `'dream'` row is a proactive notice the dream
  loop materialised from a definite dated memory event — not a user-entered
  todo. `list_tasks(source=...)` lets the `task_list` tool keep the two apart.
- `dedup_key`: a stable hash of the underlying event, so repeated dream cycles
  don't create duplicate notices. `upsert_dream_event` is idempotent on it.
A `'dream'` reminder may carry `deliver_to = NULL`: its target ("the last
active channel") is resolved by the `ReminderRunner` at delivery time, not
frozen at creation — so `due_reminders` admits NULL-target dream rows too.
"""

from __future__ import annotations

import secrets
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

_TASKS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id           TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    body         TEXT,
    due_at       REAL,
    state        TEXT NOT NULL DEFAULT 'open',
    deliver_to   TEXT,
    reminded_at  REAL,
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL,
    done_at      REAL,
    source       TEXT NOT NULL DEFAULT 'user',
    dedup_key    TEXT
);

CREATE INDEX IF NOT EXISTS idx_tasks_due
    ON tasks(due_at) WHERE state = 'open' AND reminded_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_dedup
    ON tasks(dedup_key) WHERE dedup_key IS NOT NULL;
"""

# Additive columns for DBs created before M214. CREATE TABLE IF NOT EXISTS won't
# alter an existing table, so bring older `tasks` tables up to schema in-place.
_TASKS_ADDED_COLUMNS = {
    "source": "TEXT NOT NULL DEFAULT 'user'",
    "dedup_key": "TEXT",
}


@dataclass(slots=True)
class TaskRecord:
    id: str
    title: str
    body: str | None
    due_at: float | None
    state: str  # 'open' | 'done'
    deliver_to: str | None
    reminded_at: float | None
    created_at: float
    updated_at: float
    done_at: float | None
    source: str = "user"  # 'user' | 'dream'
    dedup_key: str | None = None


def _make_task_id() -> str:
    return f"task-{int(time.time()):010d}-{secrets.token_hex(4)}"


def _row_to_record(row: sqlite3.Row) -> TaskRecord:
    return TaskRecord(
        id=row["id"],
        title=row["title"],
        body=row["body"],
        due_at=row["due_at"],
        state=row["state"],
        deliver_to=row["deliver_to"],
        reminded_at=row["reminded_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        done_at=row["done_at"],
        source=row["source"],
        dedup_key=row["dedup_key"],
    )


class TasksStore:
    """CRUD + due-reminder query over the `tasks` table."""

    def __init__(self, db_path: Path | str) -> None:
        self._path: Path | str = ":memory:" if db_path == ":memory:" else Path(db_path)
        if isinstance(self._path, Path):
            self._path.parent.mkdir(parents=True, exist_ok=True)
            target = str(self._path)
        else:
            target = self._path
        self._conn = sqlite3.connect(target, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        c = self._conn
        if self._path != ":memory:":
            c.execute("PRAGMA journal_mode = WAL")
            c.execute("PRAGMA synchronous = NORMAL")
        # Bring an older table up to schema BEFORE the CREATE/INDEX script, so
        # the partial unique index on `dedup_key` can be built on a table that
        # already has the column.
        existing = {r["name"] for r in c.execute("PRAGMA table_info(tasks)")}
        if existing:  # table pre-exists — add any missing M214 columns in place
            for name, decl in _TASKS_ADDED_COLUMNS.items():
                if name not in existing:
                    c.execute(f"ALTER TABLE tasks ADD COLUMN {name} {decl}")
        c.executescript(_TASKS_SCHEMA_SQL)

    # ---- CRUD ----

    def add_task(
        self,
        *,
        title: str,
        body: str | None = None,
        due_at: float | None = None,
        deliver_to: str | None = None,
        source: str = "user",
        dedup_key: str | None = None,
        now: float | None = None,
    ) -> TaskRecord:
        if not title.strip():
            raise ValueError("task title must be non-empty")
        at = now if now is not None else time.time()
        tid = _make_task_id()
        self._conn.execute(
            "INSERT INTO tasks (id, title, body, due_at, state, deliver_to, "
            "reminded_at, created_at, updated_at, done_at, source, dedup_key) "
            "VALUES (?, ?, ?, ?, 'open', ?, NULL, ?, ?, NULL, ?, ?)",
            (tid, title, body, due_at, deliver_to, at, at, source, dedup_key),
        )
        record = self.get_task(tid)
        assert record is not None
        return record

    def upsert_dream_event(
        self,
        *,
        dedup_key: str,
        title: str,
        body: str | None = None,
        due_at: float | None = None,
        now: float | None = None,
    ) -> TaskRecord:
        """Idempotently materialise a dream-discovered dated event as a proactive
        reminder (`source='dream'`, `deliver_to=NULL` — target resolved at
        delivery). Keyed on `dedup_key` so repeated dream cycles never duplicate
        the same event. On an existing key the mutable fields are refreshed; if
        `due_at` moved, the reminder is re-armed (`reminded_at` cleared) so it
        fires at the new time. An already-delivered notice whose time is
        unchanged is left delivered — it must not re-fire."""
        if not dedup_key:
            raise ValueError("dedup_key must be non-empty")
        if not title.strip():
            raise ValueError("task title must be non-empty")
        at = now if now is not None else time.time()
        row = self._conn.execute(
            "SELECT id, due_at FROM tasks WHERE dedup_key = ?", (dedup_key,)
        ).fetchone()
        if row is None:
            return self.add_task(
                title=title,
                body=body,
                due_at=due_at,
                deliver_to=None,
                source="dream",
                dedup_key=dedup_key,
                now=at,
            )
        rearm = row["due_at"] != due_at
        if rearm:
            self._conn.execute(
                "UPDATE tasks SET title = ?, body = ?, due_at = ?, "
                "reminded_at = NULL, state = 'open', updated_at = ? WHERE id = ?",
                (title, body, due_at, at, row["id"]),
            )
        else:
            self._conn.execute(
                "UPDATE tasks SET title = ?, body = ?, updated_at = ? WHERE id = ?",
                (title, body, at, row["id"]),
            )
        rec = self.get_task(row["id"])
        assert rec is not None
        return rec

    def get_task(self, task_id: str) -> TaskRecord | None:
        row = self._conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return _row_to_record(row) if row is not None else None

    def list_tasks(
        self,
        *,
        state: str | None = "open",
        source: str | None = None,
        limit: int = 100,
    ) -> list[TaskRecord]:
        clauses: list[str] = []
        params: list[object] = []
        if state is not None:
            clauses.append("state = ?")
            params.append(state)
        if source is not None:
            clauses.append("source = ?")
            params.append(source)
        where = f"WHERE {' AND '.join(clauses)} " if clauses else ""
        params.append(limit)
        rows = self._conn.execute(
            f"SELECT * FROM tasks {where}"
            "ORDER BY (due_at IS NULL), due_at, created_at LIMIT ?",
            params,
        ).fetchall()
        return [_row_to_record(r) for r in rows]

    def mark_done(self, task_id: str, *, now: float | None = None) -> bool:
        at = now if now is not None else time.time()
        cur = self._conn.execute(
            "UPDATE tasks SET state = 'done', done_at = ?, updated_at = ? WHERE id = ?",
            (at, at, task_id),
        )
        return cur.rowcount > 0

    def snooze(self, task_id: str, *, due_at: float, now: float | None = None) -> bool:
        """Reschedule the reminder: bump `due_at` and clear `reminded_at` so the
        sweep fires again. Re-opens a task that had already reminded."""
        at = now if now is not None else time.time()
        cur = self._conn.execute(
            "UPDATE tasks SET due_at = ?, reminded_at = NULL, state = 'open', updated_at = ? "
            "WHERE id = ?",
            (due_at, at, task_id),
        )
        return cur.rowcount > 0

    # ---- reminder sweep support ----

    def due_reminders(self, now: float) -> list[TaskRecord]:
        """Open tasks whose reminder is due and not yet delivered. The
        ReminderRunner pushes each and calls `mark_reminded`.

        A user reminder needs a concrete `deliver_to`. A `'dream'` notice may
        have `deliver_to = NULL` — its target is resolved to the last active
        channel at delivery time — so those are admitted regardless."""
        rows = self._conn.execute(
            "SELECT * FROM tasks WHERE state = 'open' AND reminded_at IS NULL "
            "AND due_at IS NOT NULL AND due_at <= ? "
            "AND (deliver_to IS NOT NULL OR source = 'dream') "
            "ORDER BY due_at",
            (now,),
        ).fetchall()
        return [_row_to_record(r) for r in rows]

    def mark_reminded(self, task_id: str, *, now: float | None = None) -> None:
        at = now if now is not None else time.time()
        self._conn.execute(
            "UPDATE tasks SET reminded_at = ?, updated_at = ? WHERE id = ?",
            (at, at, task_id),
        )

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> TasksStore:
        return self

    def __exit__(self, *exc) -> None:
        self.close()


__all__ = ["TaskRecord", "TasksStore"]
