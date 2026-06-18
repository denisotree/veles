"""M167 — human schedule DSL (daily@/weekdays@/weekend@/weekly:@) + tz."""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from veles.core.job_schedule import (
    compute_next_run,
    parse_schedule,
    resolve_schedule_tz,
)

# ---- parse + round-trip ----


def test_daily_parses():
    s = parse_schedule("daily@09:00")
    assert s.kind == "calendar"
    assert (s.at_hour, s.at_minute) == (9, 0)
    assert s.weekdays == ()
    assert parse_schedule(s.expr) == s  # round-trips


def test_weekdays_and_weekend():
    wd = parse_schedule("weekdays@18:00")
    assert wd.weekdays == (0, 1, 2, 3, 4)
    we = parse_schedule("weekend@10:30")
    assert we.weekdays == (5, 6)
    assert (we.at_hour, we.at_minute) == (10, 30)


def test_weekly_canonical_order():
    s = parse_schedule("weekly:fri,mon@09:00")
    assert s.weekdays == (0, 4)  # mon, fri (sorted)
    assert s.expr == "weekly:mon,fri@09:00"  # canonical
    assert parse_schedule(s.expr) == s


def test_other_forms_still_parse():
    assert parse_schedule("2h").kind == "interval"
    assert parse_schedule("every:30m").kind == "interval"
    assert parse_schedule("every:30m").interval_seconds == 1800
    assert parse_schedule("once:+2h").kind == "once"
    assert parse_schedule("2026-07-01T18:00:00Z").kind == "once"
    assert parse_schedule("0 9 * * *").kind == "cron"  # raw cron back-compat


def test_invalid_forms_raise():
    with pytest.raises(ValueError):
        parse_schedule("daily@25:00")  # bad hour
    with pytest.raises(ValueError):
        parse_schedule("weekly:xyz@09:00")  # bad weekday
    with pytest.raises(ValueError):
        parse_schedule("")


# ---- compute_next_run ----


def test_daily_next_run_today_then_tomorrow():
    tz = ZoneInfo("UTC")
    s = parse_schedule("daily@09:00")
    # now = 08:00 → fires today 09:00
    now = dt.datetime(2026, 6, 1, 8, 0, tzinfo=tz).timestamp()
    nxt = dt.datetime.fromtimestamp(compute_next_run(s, now=now, tz=tz), tz)
    assert (nxt.day, nxt.hour) == (1, 9)
    # now = 10:00 → fires tomorrow 09:00
    now = dt.datetime(2026, 6, 1, 10, 0, tzinfo=tz).timestamp()
    nxt = dt.datetime.fromtimestamp(compute_next_run(s, now=now, tz=tz), tz)
    assert (nxt.day, nxt.hour) == (2, 9)


def test_weekdays_skips_weekend():
    tz = ZoneInfo("UTC")
    s = parse_schedule("weekdays@09:00")
    # 2026-06-06 is a Saturday → next weekday fire is Mon 2026-06-08 09:00
    now = dt.datetime(2026, 6, 6, 12, 0, tzinfo=tz).timestamp()
    nxt = dt.datetime.fromtimestamp(compute_next_run(s, now=now, tz=tz), tz)
    assert nxt.weekday() == 0  # Monday
    assert (nxt.day, nxt.hour) == (8, 9)


def test_calendar_is_dst_correct():
    """The discriminating test: across a DST boundary, daily@09:00 fires at
    09:00 LOCAL — a fixed-offset snapshot would drift to 08:00/10:00."""
    ny = ZoneInfo("America/New_York")
    s = parse_schedule("daily@09:00")
    # US spring-forward is 2026-03-08 02:00→03:00. now = Mar 7 10:00 (after
    # 09:00, EST) → next fire is Mar 8 09:00, which is EDT (offset changed).
    now = dt.datetime(2026, 3, 7, 10, 0, tzinfo=ny).timestamp()
    back = dt.datetime.fromtimestamp(compute_next_run(s, now=now, tz=ny), ny)
    assert (back.month, back.day) == (3, 8)
    assert (back.hour, back.minute) == (9, 0)  # 09:00 local despite the DST shift


# ---- tz resolution ----


def test_resolve_tz_from_config(tmp_path, monkeypatch):
    from veles.core.context import reset_active_project, set_active_project
    from veles.core.project import init_project

    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    project = init_project(tmp_path / "proj", name="proj")
    (project.state_dir / "config.toml").write_text(
        '[schedule]\ntimezone = "Asia/Tokyo"\n', encoding="utf-8"
    )
    token = set_active_project(project)
    try:
        assert resolve_schedule_tz(project) == ZoneInfo("Asia/Tokyo")
    finally:
        reset_active_project(token)


def test_resolve_tz_defaults_to_host(tmp_path, monkeypatch):
    from veles.core.project import init_project

    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    project = init_project(tmp_path / "proj", name="proj")  # no [schedule] config
    tz = resolve_schedule_tz(project)
    assert isinstance(tz, dt.tzinfo)  # host zone, whatever the CI box is
