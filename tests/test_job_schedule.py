"""M75 — schedule parsing + next-run computation."""

from __future__ import annotations

import datetime as dt

import pytest

from veles.core.job_schedule import compute_next_run, initial_next_run, parse_schedule


def test_parse_empty_raises():
    with pytest.raises(ValueError):
        parse_schedule("")


def test_parse_interval_minutes():
    s = parse_schedule("30m")
    assert s.kind == "interval"
    assert s.expr == "30m"
    assert s.interval_seconds == 1800


def test_parse_interval_hours_and_days():
    assert parse_schedule("2h").interval_seconds == 7200
    assert parse_schedule("1d").interval_seconds == 86400
    assert parse_schedule("90s").interval_seconds == 90


def test_parse_interval_zero_raises():
    with pytest.raises(ValueError):
        parse_schedule("0m")


def test_parse_cron_valid():
    s = parse_schedule("0 9 * * *")
    assert s.kind == "cron"
    assert s.expr == "0 9 * * *"


def test_parse_cron_invalid_raises():
    with pytest.raises(ValueError):
        parse_schedule("not a cron")


def test_parse_iso_timestamp():
    s = parse_schedule("2026-06-01T09:00")
    assert s.kind == "once"
    assert s.fire_at is not None
    # Reconstruct and verify
    parsed = dt.datetime.fromtimestamp(s.fire_at, tz=dt.UTC)
    assert parsed.year == 2026
    assert parsed.month == 6
    assert parsed.day == 1


def test_parse_iso_with_z_suffix():
    s = parse_schedule("2026-06-01T09:00:00Z")
    assert s.kind == "once"
    assert s.fire_at is not None


def test_compute_next_run_for_interval():
    s = parse_schedule("30m")
    now = 1_700_000_000.0
    nxt = compute_next_run(s, now=now)
    assert nxt == now + 1800


def test_compute_next_run_for_once_returns_none():
    s = parse_schedule("2030-01-01T12:00")
    assert compute_next_run(s, now=0.0) is None


def test_compute_next_run_for_cron_advances():
    s = parse_schedule("0 9 * * *")  # daily at 09:00 UTC
    # Pick an arbitrary moment before 09:00 on a known day.
    now = dt.datetime(2026, 5, 16, 8, 0, tzinfo=dt.UTC).timestamp()
    nxt = compute_next_run(s, now=now)
    assert nxt is not None
    nxt_dt = dt.datetime.fromtimestamp(nxt, tz=dt.UTC)
    assert nxt_dt.hour == 9
    assert nxt_dt.day == 16


def test_initial_next_run_for_once_returns_fire_at():
    s = parse_schedule("2030-01-01T12:00")
    nxt = initial_next_run(s, now=0.0)
    assert nxt == s.fire_at


def test_initial_next_run_for_interval():
    s = parse_schedule("1h")
    now = 1_700_000_000.0
    assert initial_next_run(s, now=now) == now + 3600
