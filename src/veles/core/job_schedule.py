"""Job schedule parsing (M75; human DSL + tz in M167) — when a job/reminder recurs.

User-facing forms (no cron — see [[feedback_schedule_format]]):

    daily@09:00                  → every day at 09:00 (project timezone)
    weekdays@18:00               → Mon-Fri at 18:00
    weekend@10:00                → Sat-Sun at 10:00
    weekly:mon,fri@09:00         → those weekdays at 09:00
    30m | 2h | 1d | every:2h     → fixed interval from now
    once:2026-07-01 18:00 | +2h  → one-shot
    2026-07-01T18:00Z            → one-shot (ISO)

Calendar forms fire at a WALL-CLOCK time in the project's timezone — the
host's by default, overridable with `[schedule] timezone = "Europe/Moscow"`
in config.toml (`resolve_schedule_tz`). They are computed directly with
`zoneinfo.ZoneInfo` so they stay correct across DST (a fixed UTC offset would
drift an hour at the boundary); cron is NOT used for them.

Raw 5-field cron (`0 9 * * *`) is still accepted for back-compat but is no
longer the documented form and is computed in UTC via croniter.

`parse_schedule` produces a `Schedule`; `compute_next_run(schedule, now, tz)`
returns the next absolute unix timestamp (None when a `once` already fired).
The canonical `expr` round-trips: `parse_schedule(s.expr)` reproduces `s`.
"""

from __future__ import annotations

import datetime as dt
import os
import re
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter

_INTERVAL_RE = re.compile(r"^\s*(\d+)\s*([smhd])\s*$", re.IGNORECASE)
_INTERVAL_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}

# Calendar DSL — Python weekday() numbering (Mon=0 … Sun=6).
_DAY_NUM = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
_NUM_DAY = {v: k for k, v in _DAY_NUM.items()}
_WEEKDAYS = (0, 1, 2, 3, 4)
_WEEKEND = (5, 6)
_CAL_RE = re.compile(
    r"^(?P<head>daily|weekdays|weekend|weekly:(?P<days>[a-z,]+))@(?P<h>\d{1,2}):(?P<m>\d{2})$",
    re.IGNORECASE,
)


@dataclass(slots=True, frozen=True)
class Schedule:
    kind: str  # 'calendar' | 'interval' | 'once' | 'cron'
    expr: str  # canonical re-rendered form (round-trips through parse_schedule)
    interval_seconds: int | None = None
    fire_at: float | None = None  # 'once'
    at_hour: int | None = None  # 'calendar'
    at_minute: int | None = None  # 'calendar'
    # 'calendar': allowed Python weekdays (Mon=0..Sun=6); () = every day.
    weekdays: tuple[int, ...] = ()

    def display(self) -> str:
        if self.kind == "calendar":
            return self.expr
        if self.kind == "interval":
            return f"every {self.expr}"
        if self.kind == "cron":
            return f"cron: {self.expr}"
        if self.kind == "once":
            assert self.fire_at is not None
            return f"once at {dt.datetime.fromtimestamp(self.fire_at, tz=dt.UTC).isoformat()}"
        return self.expr


def _parse_calendar(s: str) -> Schedule | None:
    m = _CAL_RE.match(s)
    if m is None:
        return None
    h, mi = int(m.group("h")), int(m.group("m"))
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        raise ValueError(f"invalid time in schedule {s!r} (use HH:MM, 00:00-23:59)")
    head = m.group("head").lower()
    if head == "daily":
        days: tuple[int, ...] = ()
        canon_head = "daily"
    elif head == "weekdays":
        days, canon_head = _WEEKDAYS, "weekdays"
    elif head == "weekend":
        days, canon_head = _WEEKEND, "weekend"
    else:  # weekly:<days>
        names = [d.strip() for d in (m.group("days") or "").lower().split(",") if d.strip()]
        try:
            nums = sorted({_DAY_NUM[n] for n in names})
        except KeyError as exc:
            raise ValueError(f"unknown weekday in {s!r}: {exc}; use mon..sun") from exc
        if not nums:
            raise ValueError(f"weekly schedule needs at least one day: {s!r}")
        days = tuple(nums)
        canon_head = "weekly:" + ",".join(_NUM_DAY[n] for n in nums)
    return Schedule(
        kind="calendar",
        expr=f"{canon_head}@{h:02d}:{mi:02d}",
        at_hour=h,
        at_minute=mi,
        weekdays=days,
    )


def _parse_interval(s: str) -> Schedule | None:
    m = _INTERVAL_RE.match(s)
    if m is None:
        return None
    n = int(m.group(1))
    if n <= 0:
        raise ValueError(f"interval must be > 0: {s!r}")
    unit = m.group(2).lower()
    return Schedule(kind="interval", expr=f"{n}{unit}", interval_seconds=n * _INTERVAL_UNITS[unit])


def _parse_once(when: str) -> Schedule:
    from veles.core.autopilot import parse_until  # +2h / ISO / epoch / 'YYYY-MM-DD HH:MM'

    return Schedule(kind="once", expr=f"once:{when}", fire_at=parse_until(when))


def parse_schedule(expr: str, *, now: float | None = None) -> Schedule:
    """Detect the schedule shape and produce a normalized Schedule.

    Order: calendar DSL -> `every:` -> `once:` -> bare ISO -> bare interval ->
    raw cron (back-compat). Raises ValueError on anything unrecognised.
    """
    del now  # accepted for signature stability; detection is now-independent
    s = (expr or "").strip()
    if not s:
        raise ValueError("schedule expression is empty")
    low = s.lower()

    cal = _parse_calendar(s)
    if cal is not None:
        return cal

    if low.startswith("every:"):
        iv = _parse_interval(s[len("every:") :].strip())
        if iv is None:
            raise ValueError(f"unrecognised interval in {s!r}; use every:30m / every:2h / every:1d")
        return iv

    if low.startswith("once:"):
        return _parse_once(s[len("once:") :].strip())

    if "T" in s or s.endswith("Z"):  # bare ISO one-shot (back-compat)
        try:
            parsed = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"invalid ISO timestamp: {s!r}") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.UTC)
        return Schedule(kind="once", expr=s, fire_at=parsed.timestamp())

    iv = _parse_interval(s)  # bare interval (back-compat: 30m / 2h / 1d)
    if iv is not None:
        return iv

    try:  # raw cron (back-compat, undocumented)
        croniter(s, dt.datetime.now(tz=dt.UTC))
    except (ValueError, KeyError) as exc:
        raise ValueError(
            f"unrecognised schedule {s!r}; use daily@09:00 / weekdays@18:00 / "
            "weekly:mon,fri@09:00 / every:2h / once:<when>"
        ) from exc
    return Schedule(kind="cron", expr=s)


def _host_tz() -> dt.tzinfo:
    """Best-effort host IANA zone (DST-aware). Falls back to a fixed offset
    (correct *now* but would drift across DST — last resort only)."""
    name = os.environ.get("TZ")
    if name:
        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            pass
    try:  # macOS/Linux: /etc/localtime -> /usr/share/zoneinfo/<Zone>
        link = os.readlink("/etc/localtime")
        if "zoneinfo/" in link:
            return ZoneInfo(link.split("zoneinfo/", 1)[1])
    except (OSError, ValueError, ZoneInfoNotFoundError):
        pass
    return dt.datetime.now().astimezone().tzinfo or dt.UTC


def resolve_schedule_tz(project=None) -> dt.tzinfo:
    """The timezone calendar schedules fire in: the project's
    `[schedule] timezone` config override if set, else the host zone."""
    if project is not None:
        try:
            from veles.core.project_config import get_section, load_project_config

            name = get_section(load_project_config(project), "schedule").get("timezone")
            if name:
                return ZoneInfo(str(name))
        except Exception:  # best-effort — a bad config tz must not break scheduling
            pass
    return _host_tz()


def compute_next_run(
    schedule: Schedule, *, now: float, tz: dt.tzinfo | None = None
) -> float | None:
    """Return next-fire unix timestamp, or None if the schedule is done."""
    if schedule.kind == "once":
        return None
    if schedule.kind == "interval":
        assert schedule.interval_seconds is not None
        return now + schedule.interval_seconds
    if schedule.kind == "calendar":
        assert schedule.at_hour is not None and schedule.at_minute is not None
        zone = tz or _host_tz()
        # Date arithmetic (not aware-datetime + timedelta) so DST never shifts
        # the day; the wall-clock time is realised via ZoneInfo per candidate.
        base_date = dt.datetime.fromtimestamp(now, zone).date()
        for add in range(8):
            d = base_date + dt.timedelta(days=add)
            cand = dt.datetime(
                d.year, d.month, d.day, schedule.at_hour, schedule.at_minute, tzinfo=zone
            )
            ts = cand.timestamp()
            if ts > now and (not schedule.weekdays or cand.weekday() in schedule.weekdays):
                return ts
        return None  # unreachable for a valid weekday set
    if schedule.kind == "cron":
        base = dt.datetime.fromtimestamp(now, tz=dt.UTC)
        return float(croniter(schedule.expr, base).get_next())
    raise ValueError(f"unknown schedule kind: {schedule.kind!r}")


def initial_next_run(schedule: Schedule, *, now: float, tz: dt.tzinfo | None = None) -> float:
    """Compute the very first next_run when a job is created."""
    if schedule.kind == "once":
        assert schedule.fire_at is not None
        return schedule.fire_at
    nxt = compute_next_run(schedule, now=now, tz=tz)
    assert nxt is not None
    return nxt


__all__ = [
    "Schedule",
    "compute_next_run",
    "initial_next_run",
    "parse_schedule",
    "resolve_schedule_tz",
]
