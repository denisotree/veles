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
    done_at      REAL
);

CREATE INDEX IF NOT EXISTS idx_tasks_due
    ON tasks(due_at) WHERE state = 'open' AND reminded_at IS NULL;
"""


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
        c.executescript(_TASKS_SCHEMA_SQL)

    # ---- CRUD ----

    def add_task(
        self,
        *,
        title: str,
        body: str | None = None,
        due_at: float | None = None,
        deliver_to: str | None = None,
        now: float | None = None,
    ) -> TaskRecord:
        if not title.strip():
            raise ValueError("task title must be non-empty")
        at = now if now is not None else time.time()
        tid = _make_task_id()
        self._conn.execute(
            "INSERT INTO tasks (id, title, body, due_at, state, deliver_to, "
            "reminded_at, created_at, updated_at, done_at) "
            "VALUES (?, ?, ?, ?, 'open', ?, NULL, ?, ?, NULL)",
            (tid, title, body, due_at, deliver_to, at, at),
        )
        record = self.get_task(tid)
        assert record is not None
        return record

    def get_task(self, task_id: str) -> TaskRecord | None:
        row = self._conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return _row_to_record(row) if row is not None else None

    def list_tasks(self, *, state: str | None = "open", limit: int = 100) -> list[TaskRecord]:
        if state is None:
            rows = self._conn.execute(
                "SELECT * FROM tasks ORDER BY (due_at IS NULL), due_at, created_at LIMIT ?",
                (limit,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM tasks WHERE state = ? "
                "ORDER BY (due_at IS NULL), due_at, created_at LIMIT ?",
                (state, limit),
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
        """Open tasks whose reminder is due and not yet delivered, with a
        target to deliver to. The ReminderRunner pushes each and calls
        `mark_reminded`."""
        rows = self._conn.execute(
            "SELECT * FROM tasks WHERE state = 'open' AND reminded_at IS NULL "
            "AND due_at IS NOT NULL AND due_at <= ? AND deliver_to IS NOT NULL "
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
