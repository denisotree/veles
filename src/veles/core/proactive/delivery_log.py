"""Proactive-delivery audit log (M214).

Every attempt the `ReminderRunner` makes to push a notice is recorded here —
target, whether it succeeded, and why it failed. Two reasons this exists:

1. It closes the root of the "self-diagnosis can't be trusted" failure: an
   agent asked "did my reminder go out?" has a factual log to read (via the
   `proactive_status` tool) instead of fabricating an answer.
2. Cold-start retries and channel-down retries become visible instead of
   silent.

Shares the project `memory.db` (one DB per project). Tiny append + tail-read
surface — the sweep loop lives in `ReminderRunner`, not here.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS proactive_deliveries (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         REAL NOT NULL,
    target     TEXT,
    dedup_key  TEXT,
    ok         INTEGER NOT NULL,
    reason     TEXT
);

CREATE INDEX IF NOT EXISTS idx_deliveries_ts ON proactive_deliveries(ts);
"""


@dataclass(slots=True)
class DeliveryAttempt:
    ts: float
    target: str | None
    dedup_key: str | None
    ok: bool
    reason: str | None


class DeliveryLog:
    """Append-only audit of proactive delivery attempts."""

    def __init__(self, db_path: Path | str) -> None:
        self._path: Path | str = ":memory:" if db_path == ":memory:" else Path(db_path)
        if isinstance(self._path, Path):
            self._path.parent.mkdir(parents=True, exist_ok=True)
            target = str(self._path)
        else:
            target = self._path
        self._conn = sqlite3.connect(target, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        if self._path != ":memory:":
            self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.execute("PRAGMA synchronous = NORMAL")
        self._conn.executescript(_SCHEMA_SQL)

    def record(
        self,
        *,
        target: str | None,
        dedup_key: str | None,
        ok: bool,
        reason: str | None = None,
        now: float | None = None,
    ) -> None:
        self._conn.execute(
            "INSERT INTO proactive_deliveries (ts, target, dedup_key, ok, reason) "
            "VALUES (?, ?, ?, ?, ?)",
            (now if now is not None else time.time(), target, dedup_key, 1 if ok else 0, reason),
        )

    def recent(self, *, limit: int = 20) -> list[DeliveryAttempt]:
        rows = self._conn.execute(
            "SELECT * FROM proactive_deliveries ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [
            DeliveryAttempt(
                ts=r["ts"],
                target=r["target"],
                dedup_key=r["dedup_key"],
                ok=bool(r["ok"]),
                reason=r["reason"],
            )
            for r in rows
        ]

    def close(self) -> None:
        self._conn.close()


__all__ = ["DeliveryAttempt", "DeliveryLog"]
