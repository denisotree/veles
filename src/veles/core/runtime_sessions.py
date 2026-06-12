"""RuntimeSessionStore (M134) — the project's registry of long-lived agent runtimes.

A *runtime session* is a long-lived agent runtime bound to the project, with
its own fixed settings (model/provider/host/port/mode) and a lifecycle. Two
kinds today:

- ``daemon`` — a background `veles daemon` process (channel-attachable, M136);
- ``tui``    — the interactive `veles` terminal session (M138).

This sits one level **above** the conversation layer: a runtime session hosts
many `SessionStore` conversation sessions (one per channel/thread). It shares
the project's `memory.db` (one DB per project keeps backup/export simple),
mirroring `JobsStore`'s self-contained pattern.

Settings here are a *runtime cache* of what the session was launched with; the
declarative source-of-truth for a daemon's settings is `config.toml`
(`[daemon.<name>]`, M134) which a restart re-reads. Deletion is **soft**
(`deleted_at` stamped) — the row is hidden from listings but kept so its
history can still feed curator/dreaming (M135).
"""

from __future__ import annotations

import secrets
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

VALID_KINDS = ("daemon", "tui")
VALID_STATUS = ("created", "running", "stopped", "error")

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS runtime_sessions (
    id               TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    kind             TEXT NOT NULL,           -- 'daemon' | 'tui'
    model            TEXT,
    provider         TEXT,
    host             TEXT,
    port             INTEGER,
    mode             TEXT,
    status           TEXT NOT NULL DEFAULT 'created',
    pid              INTEGER,
    created_at       REAL NOT NULL,
    last_started_at  REAL,
    last_stopped_at  REAL,
    deleted_at       REAL                     -- NULL = active; set = soft-deleted
);

-- One live (non-deleted) session per (name, kind) within a project.
CREATE UNIQUE INDEX IF NOT EXISTS idx_runtime_sessions_name
    ON runtime_sessions(name, kind) WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_runtime_sessions_kind
    ON runtime_sessions(kind, deleted_at);
"""


@dataclass(slots=True)
class RuntimeSessionRecord:
    id: str
    name: str
    kind: str
    model: str | None
    provider: str | None
    host: str | None
    port: int | None
    mode: str | None
    status: str
    pid: int | None
    created_at: float
    last_started_at: float | None
    last_stopped_at: float | None
    deleted_at: float | None

    @property
    def deleted(self) -> bool:
        return self.deleted_at is not None


class RuntimeSessionExists(Exception):
    """A live runtime session with this (name, kind) already exists."""


def _make_id() -> str:
    return f"rt-{int(time.time()):010d}-{secrets.token_hex(4)}"


def _row(r: sqlite3.Row) -> RuntimeSessionRecord:
    return RuntimeSessionRecord(
        id=r["id"],
        name=r["name"],
        kind=r["kind"],
        model=r["model"],
        provider=r["provider"],
        host=r["host"],
        port=r["port"],
        mode=r["mode"],
        status=r["status"],
        pid=r["pid"],
        created_at=r["created_at"],
        last_started_at=r["last_started_at"],
        last_stopped_at=r["last_stopped_at"],
        deleted_at=r["deleted_at"],
    )


class RuntimeSessionStore:
    """CRUD + lifecycle over the `runtime_sessions` table (one per project)."""

    def __init__(self, db_path: Path | str) -> None:
        self._path: Path | str = ":memory:" if db_path == ":memory:" else Path(db_path)
        if isinstance(self._path, Path):
            self._path.parent.mkdir(parents=True, exist_ok=True)
            target = str(self._path)
        else:
            target = self._path
        self._conn = sqlite3.connect(target, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        c = self._conn
        if self._path != ":memory:":
            c.execute("PRAGMA journal_mode = WAL")
            c.execute("PRAGMA synchronous = NORMAL")
            c.execute("PRAGMA busy_timeout = 5000")
        c.executescript(_SCHEMA_SQL)

    # ---- CRUD ----

    def create(
        self,
        name: str,
        kind: str,
        *,
        model: str | None = None,
        provider: str | None = None,
        host: str | None = None,
        port: int | None = None,
        mode: str | None = None,
        status: str = "created",
        now: float | None = None,
    ) -> RuntimeSessionRecord:
        if kind not in VALID_KINDS:
            raise ValueError(f"invalid runtime-session kind: {kind!r}")
        if not name.strip():
            raise ValueError("runtime-session name must be non-empty")
        if self.get_by_name(name, kind=kind) is not None:
            raise RuntimeSessionExists(f"{kind} session {name!r} already exists")
        rid = _make_id()
        ts = time.time() if now is None else now
        self._conn.execute(
            "INSERT INTO runtime_sessions "
            "(id, name, kind, model, provider, host, port, mode, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (rid, name, kind, model, provider, host, port, mode, status, ts),
        )
        rec = self.get(rid)
        assert rec is not None
        return rec

    def get(self, rid: str) -> RuntimeSessionRecord | None:
        r = self._conn.execute("SELECT * FROM runtime_sessions WHERE id = ?", (rid,)).fetchone()
        return _row(r) if r is not None else None

    def get_by_name(
        self, name: str, *, kind: str | None = None, include_deleted: bool = False
    ) -> RuntimeSessionRecord | None:
        q = "SELECT * FROM runtime_sessions WHERE name = ?"
        params: list = [name]
        if kind is not None:
            q += " AND kind = ?"
            params.append(kind)
        if not include_deleted:
            q += " AND deleted_at IS NULL"
        q += " ORDER BY created_at DESC LIMIT 1"
        r = self._conn.execute(q, tuple(params)).fetchone()
        return _row(r) if r is not None else None

    def list(
        self, *, kind: str | None = None, include_deleted: bool = False
    ) -> list[RuntimeSessionRecord]:
        q = "SELECT * FROM runtime_sessions"
        clauses: list[str] = []
        params: list = []
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind)
        if not include_deleted:
            clauses.append("deleted_at IS NULL")
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY created_at ASC"
        return [_row(r) for r in self._conn.execute(q, tuple(params)).fetchall()]

    # ---- lifecycle ----

    def update_settings(
        self,
        rid: str,
        *,
        model: str | None = None,
        provider: str | None = None,
        host: str | None = None,
        port: int | None = None,
        mode: str | None = None,
    ) -> None:
        """Refresh the runtime cache of settings (e.g. after a restart that
        re-read `config.toml`). Only non-None values are written."""
        fields = {
            "model": model,
            "provider": provider,
            "host": host,
            "port": port,
            "mode": mode,
        }
        sets = [(k, v) for k, v in fields.items() if v is not None]
        if not sets:
            return
        assignments = ", ".join(f"{k} = ?" for k, _ in sets)
        self._conn.execute(
            f"UPDATE runtime_sessions SET {assignments} WHERE id = ?",
            (*[v for _, v in sets], rid),
        )

    def mark_started(self, rid: str, *, pid: int | None = None, now: float | None = None) -> None:
        ts = time.time() if now is None else now
        self._conn.execute(
            "UPDATE runtime_sessions SET status = 'running', pid = ?, last_started_at = ? "
            "WHERE id = ?",
            (pid, ts, rid),
        )

    def mark_stopped(self, rid: str, *, status: str = "stopped", now: float | None = None) -> None:
        if status not in VALID_STATUS:
            raise ValueError(f"invalid status: {status!r}")
        ts = time.time() if now is None else now
        self._conn.execute(
            "UPDATE runtime_sessions SET status = ?, pid = NULL, last_stopped_at = ? WHERE id = ?",
            (status, ts, rid),
        )

    def soft_delete(self, rid: str, *, now: float | None = None) -> bool:
        """Mark deleted (hidden from listings) but keep the row + history so
        curator/dreaming can still consume it (M135). Returns False if the
        id is unknown or already deleted."""
        ts = time.time() if now is None else now
        cur = self._conn.execute(
            "UPDATE runtime_sessions SET deleted_at = ?, status = 'stopped', pid = NULL "
            "WHERE id = ? AND deleted_at IS NULL",
            (ts, rid),
        )
        return cur.rowcount > 0

    def close(self) -> None:
        self._conn.close()


def runtime_session_digest(records: list[RuntimeSessionRecord]) -> str | None:
    """Render a markdown digest of every runtime session ever launched in a
    project — active and soft-deleted (M135-dream / ISSUES 3a). Pass
    `RuntimeSessionStore.list(include_deleted=True)`. Returns None when there
    are no records (nothing to feed the dream).

    The point: ISSUES 3a wants "records of all sessions that were ever launched
    … used for dreaming of active daemons" — so a soft-deleted daemon's
    existence + settings persist into the learnable corpus rather than vanishing
    from the list."""
    if not records:
        return None
    lines = ["# Daemon/TUI runtime sessions (all launched, incl. deleted)", ""]
    for r in sorted(records, key=lambda x: x.created_at):
        flag = " — DELETED" if r.deleted else ""
        model = f"{r.provider or '?'}:{r.model}" if r.model else (r.provider or "—")
        port = f" port={r.port}" if r.port is not None else ""
        lines.append(f"- **{r.name}** ({r.kind}){flag}: status={r.status} model={model}{port}")
    return "\n".join(lines)
