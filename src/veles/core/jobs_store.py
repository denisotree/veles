"""JobsStore (M75) — SQLite-backed scheduled jobs + run history.

Shares the project's `memory.db` with `SessionStore` (one DB per project keeps
backup/export simple). Two tables added on first open:

    jobs       — one row per scheduled job (id, prompt, schedule, deliver_to,
                 next_run_at, last_run_at, last_status, last_output_path, …)
    job_runs   — one row per execution (job_id, run_id, status, output_path)

Schema is forward-only: `PRAGMA user_version` is bumped to 3 when jobs tables
are created. Existing v2 databases (M58 FTS5) are upgraded in-place.

Methods are intentionally small — CRUD + due-job query + run lifecycle. No
embedded scheduling logic: callers (JobRunner, CLI) own the tick loop.
"""

from __future__ import annotations

import json
import secrets
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from veles.core.job_schedule import Schedule, initial_next_run, parse_schedule

_JOBS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    id                  TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    prompt              TEXT NOT NULL,
    schedule_kind       TEXT NOT NULL,
    schedule_expr       TEXT NOT NULL,
    schedule_meta_json  TEXT,
    repeat_times        INTEGER,
    repeat_completed    INTEGER NOT NULL DEFAULT 0,
    context_from        TEXT,
    deliver_to          TEXT,
    enabled             INTEGER NOT NULL DEFAULT 1,
    state               TEXT NOT NULL DEFAULT 'scheduled',
    created_at          REAL NOT NULL,
    next_run_at         REAL NOT NULL,
    last_run_at         REAL,
    last_status         TEXT,
    last_error          TEXT,
    last_output_path    TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_due
    ON jobs(next_run_at) WHERE enabled = 1 AND state = 'scheduled';

CREATE TABLE IF NOT EXISTS job_runs (
    run_id              TEXT PRIMARY KEY,
    job_id              TEXT NOT NULL,
    started_at          REAL NOT NULL,
    finished_at         REAL,
    status              TEXT NOT NULL,
    iterations          INTEGER,
    output_path         TEXT,
    error               TEXT,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_job_runs_by_job
    ON job_runs(job_id, started_at DESC);
"""

_JOBS_USER_VERSION = 3


@dataclass(slots=True)
class JobRecord:
    id: str
    name: str
    prompt: str
    schedule: Schedule
    repeat_times: int | None
    repeat_completed: int
    context_from: str | None
    deliver_to: str | None
    enabled: bool
    state: str  # 'scheduled' | 'paused' | 'error' | 'done'
    created_at: float
    next_run_at: float
    last_run_at: float | None
    last_status: str | None
    last_error: str | None
    last_output_path: str | None


@dataclass(slots=True, frozen=True)
class JobRunRecord:
    run_id: str
    job_id: str
    started_at: float
    finished_at: float | None
    status: str
    iterations: int | None
    output_path: str | None
    error: str | None


def _make_job_id() -> str:
    return f"job-{int(time.time()):010d}-{secrets.token_hex(4)}"


def _make_run_id() -> str:
    return f"jrun-{int(time.time()):010d}-{secrets.token_hex(4)}"


class JobsStore:
    """CRUD + lifecycle ops over the jobs / job_runs tables."""

    def __init__(self, db_path: Path | str) -> None:
        self._path: Path | str = ":memory:" if db_path == ":memory:" else Path(db_path)
        if isinstance(self._path, Path):
            self._path.parent.mkdir(parents=True, exist_ok=True)
            target = str(self._path)
        else:
            target = self._path
        self._conn = sqlite3.connect(
            target,
            check_same_thread=False,
            isolation_level=None,
        )
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        c = self._conn
        c.execute("PRAGMA foreign_keys = ON")
        if self._path != ":memory:":
            c.execute("PRAGMA journal_mode = WAL")
            c.execute("PRAGMA synchronous = NORMAL")
        c.executescript(_JOBS_SCHEMA_SQL)
        current = c.execute("PRAGMA user_version").fetchone()[0]
        if current < _JOBS_USER_VERSION:
            c.execute(f"PRAGMA user_version = {_JOBS_USER_VERSION}")

    # ---- CRUD ----

    def add_job(
        self,
        *,
        name: str,
        prompt: str,
        schedule_expr: str,
        repeat_times: int | None = None,
        context_from: str | None = None,
        deliver_to: str | None = None,
        enabled: bool = True,
        now: float | None = None,
    ) -> JobRecord:
        if not name.strip():
            raise ValueError("job name must be non-empty")
        if not prompt.strip():
            raise ValueError("job prompt must be non-empty")
        sched = parse_schedule(schedule_expr)
        at = now if now is not None else time.time()
        next_at = initial_next_run(sched, now=at)
        jid = _make_job_id()
        meta = (
            json.dumps({"fire_at": sched.fire_at, "interval_seconds": sched.interval_seconds})
            if sched.fire_at is not None or sched.interval_seconds is not None
            else None
        )
        with self._tx():
            self._conn.execute(
                """
                INSERT INTO jobs
                  (id, name, prompt, schedule_kind, schedule_expr, schedule_meta_json,
                   repeat_times, repeat_completed, context_from, deliver_to, enabled,
                   state, created_at, next_run_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    jid,
                    name,
                    prompt,
                    sched.kind,
                    sched.expr,
                    meta,
                    repeat_times,
                    0,
                    context_from,
                    deliver_to,
                    1 if enabled else 0,
                    "scheduled",
                    at,
                    next_at,
                ),
            )
        rec = self.get_job(jid)
        assert rec is not None
        return rec

    def get_job(self, job_id: str) -> JobRecord | None:
        row = self._conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return _row_to_job(row) if row else None

    def list_jobs(self, *, include_disabled: bool = True) -> list[JobRecord]:
        sql = "SELECT * FROM jobs"
        if not include_disabled:
            sql += " WHERE enabled = 1"
        sql += " ORDER BY created_at DESC"
        return [_row_to_job(r) for r in self._conn.execute(sql).fetchall()]

    def due_jobs(self, now: float, *, limit: int = 50) -> list[JobRecord]:
        rows = self._conn.execute(
            """
            SELECT * FROM jobs
             WHERE enabled = 1 AND state = 'scheduled' AND next_run_at <= ?
             ORDER BY next_run_at ASC LIMIT ?
            """,
            (now, limit),
        ).fetchall()
        return [_row_to_job(r) for r in rows]

    def update_job(self, job_id: str, **fields: object) -> bool:
        if not fields:
            return False
        allowed = {
            "name",
            "prompt",
            "context_from",
            "deliver_to",
            "enabled",
            "state",
            "next_run_at",
            "last_run_at",
            "last_status",
            "last_error",
            "last_output_path",
            "repeat_times",
            "repeat_completed",
        }
        bad = set(fields) - allowed
        if bad:
            raise ValueError(f"update_job: unknown columns {sorted(bad)}")
        # Coerce booleans for `enabled`.
        if "enabled" in fields:
            fields["enabled"] = 1 if fields["enabled"] else 0
        setters = ", ".join(f"{k}=?" for k in fields)
        values = [*list(fields.values()), job_id]
        with self._tx():
            cur = self._conn.execute(f"UPDATE jobs SET {setters} WHERE id=?", values)
        return cur.rowcount > 0

    def delete_job(self, job_id: str) -> bool:
        with self._tx():
            cur = self._conn.execute("DELETE FROM jobs WHERE id=?", (job_id,))
        return cur.rowcount > 0

    def trigger_job(self, job_id: str, *, now: float | None = None) -> bool:
        """Force next_run_at to `now` so the runner picks it up on next tick."""
        at = now if now is not None else time.time()
        return self.update_job(job_id, next_run_at=at, state="scheduled", enabled=True)

    # ---- run lifecycle ----

    def mark_run_started(self, *, job_id: str, started_at: float | None = None) -> str:
        rid = _make_run_id()
        at = started_at if started_at is not None else time.time()
        with self._tx():
            self._conn.execute(
                """
                INSERT INTO job_runs (run_id, job_id, started_at, status)
                VALUES (?,?,?,'running')
                """,
                (rid, job_id, at),
            )
        return rid

    def mark_run_finished(
        self,
        *,
        run_id: str,
        status: str,
        iterations: int | None = None,
        output_path: str | None = None,
        error: str | None = None,
        finished_at: float | None = None,
    ) -> bool:
        at = finished_at if finished_at is not None else time.time()
        with self._tx():
            cur = self._conn.execute(
                """
                UPDATE job_runs
                   SET finished_at=?, status=?, iterations=?, output_path=?, error=?
                 WHERE run_id=?
                """,
                (at, status, iterations, output_path, error, run_id),
            )
        return cur.rowcount > 0

    def list_runs(self, job_id: str, *, limit: int = 20) -> list[JobRunRecord]:
        rows = self._conn.execute(
            """
            SELECT * FROM job_runs WHERE job_id=?
             ORDER BY started_at DESC LIMIT ?
            """,
            (job_id, limit),
        ).fetchall()
        return [
            JobRunRecord(
                run_id=r["run_id"],
                job_id=r["job_id"],
                started_at=float(r["started_at"]),
                finished_at=float(r["finished_at"]) if r["finished_at"] is not None else None,
                status=r["status"],
                iterations=int(r["iterations"]) if r["iterations"] is not None else None,
                output_path=r["output_path"],
                error=r["error"],
            )
            for r in rows
        ]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> JobsStore:
        return self

    def __exit__(self, *exc: object) -> None:
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


def _row_to_job(row: sqlite3.Row) -> JobRecord:
    meta = json.loads(row["schedule_meta_json"]) if row["schedule_meta_json"] else {}
    sched = Schedule(
        kind=row["schedule_kind"],
        expr=row["schedule_expr"],
        interval_seconds=meta.get("interval_seconds"),
        fire_at=meta.get("fire_at"),
    )
    return JobRecord(
        id=row["id"],
        name=row["name"],
        prompt=row["prompt"],
        schedule=sched,
        repeat_times=row["repeat_times"],
        repeat_completed=int(row["repeat_completed"]),
        context_from=row["context_from"],
        deliver_to=row["deliver_to"],
        enabled=bool(row["enabled"]),
        state=row["state"],
        created_at=float(row["created_at"]),
        next_run_at=float(row["next_run_at"]),
        last_run_at=float(row["last_run_at"]) if row["last_run_at"] is not None else None,
        last_status=row["last_status"],
        last_error=row["last_error"],
        last_output_path=row["last_output_path"],
    )


__all__ = ["JobRecord", "JobRunRecord", "JobsStore"]
