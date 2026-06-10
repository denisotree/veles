"""Job schedule parsing (M75) — cron / interval / once expressions.

Three accepted syntaxes:

    "0 9 * * *"                  → cron (5-field croniter)
    "30m" | "2h" | "1d"          → interval (delta from now)
    "2026-06-01T09:00"           → one-shot ISO-8601 timestamp

The parser produces a `Schedule` dataclass; `compute_next_run(schedule, now)`
returns the next absolute unix timestamp. For one-shot jobs that already
fired, `compute_next_run` returns `None` — the runner uses that signal to
mark the job done.

Why these three: cron covers "every day at 9", interval covers "every 30
minutes", once covers "send me a reminder at this specific time". A
full ad-hoc DSL is overkill — three forms cover 95% of practical scheduling.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

from croniter import croniter

_INTERVAL_RE = re.compile(r"^\s*(\d+)\s*([smhd])\s*$", re.IGNORECASE)
_INTERVAL_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


@dataclass(slots=True, frozen=True)
class Schedule:
    kind: str  # 'cron' | 'interval' | 'once'
    expr: str  # canonical re-rendered form
    interval_seconds: int | None = None
    fire_at: float | None = None  # only set for 'once'

    def display(self) -> str:
        if self.kind == "cron":
            return f"cron: {self.expr}"
        if self.kind == "interval":
            return f"every {self.expr}"
        if self.kind == "once":
            assert self.fire_at is not None
            iso = dt.datetime.fromtimestamp(self.fire_at, tz=dt.UTC).isoformat()
            return f"once at {iso}"
        return self.expr


def parse_schedule(expr: str, *, now: float | None = None) -> Schedule:
    """Detect the schedule shape and produce a normalized Schedule.

    Order of detection: ISO timestamp → interval → cron. ISO must contain a
    'T'; interval is `<num><unit>`; everything else is treated as a cron
    expression and validated by `croniter`.
    """
    s = (expr or "").strip()
    if not s:
        raise ValueError("schedule expression is empty")

    if "T" in s or s.endswith("Z"):
        try:
            parsed = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"invalid ISO timestamp: {s!r}") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.UTC)
        return Schedule(kind="once", expr=s, fire_at=parsed.timestamp())

    m = _INTERVAL_RE.match(s)
    if m:
        n = int(m.group(1))
        unit = m.group(2).lower()
        if n <= 0:
            raise ValueError(f"interval must be > 0: {s!r}")
        return Schedule(
            kind="interval",
            expr=f"{n}{unit}",
            interval_seconds=n * _INTERVAL_UNITS[unit],
        )

    try:
        # Validate by constructing croniter; raises if malformed.
        croniter(s, dt.datetime.now(tz=dt.UTC))
    except (ValueError, KeyError) as exc:
        raise ValueError(f"unrecognised schedule {s!r}: {exc}") from exc
    return Schedule(kind="cron", expr=s)


def compute_next_run(schedule: Schedule, *, now: float) -> float | None:
    """Return next-fire unix timestamp, or None if the schedule is done."""
    if schedule.kind == "once":
        # Once-jobs fire when fire_at > last_run; the runner consumes this
        # by setting next_run_at = fire_at on creation and to None on completion.
        return None
    if schedule.kind == "interval":
        assert schedule.interval_seconds is not None
        return now + schedule.interval_seconds
    if schedule.kind == "cron":
        base = dt.datetime.fromtimestamp(now, tz=dt.UTC)
        itr = croniter(schedule.expr, base)
        return float(itr.get_next())
    raise ValueError(f"unknown schedule kind: {schedule.kind!r}")


def initial_next_run(schedule: Schedule, *, now: float) -> float:
    """Compute the very first next_run when a job is created.

    For `once`, it's `fire_at`. For `interval`, `now + interval`. For
    `cron`, the next matching tick after `now`.
    """
    if schedule.kind == "once":
        assert schedule.fire_at is not None
        return schedule.fire_at
    nxt = compute_next_run(schedule, now=now)
    assert nxt is not None
    return nxt


__all__ = [
    "Schedule",
    "compute_next_run",
    "initial_next_run",
    "parse_schedule",
]
