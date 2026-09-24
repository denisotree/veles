"""Timestamp formats: one for state files and logs, one for what the user reads."""

from __future__ import annotations

import time


def utc_iso(ts: float | None = None) -> str:
    """`2026-09-23T10:00:00Z` for `ts` (seconds since the epoch), or for now."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def local_stamp(ts: float, *, seconds: bool = False) -> str:
    """`2026-09-23 13:00` (or `…13:00:00`) in the user's local time zone —
    for listings a person reads (sessions, tools, jobs)."""
    return time.strftime("%Y-%m-%d %H:%M:%S" if seconds else "%Y-%m-%d %H:%M", time.localtime(ts))


__all__ = ["local_stamp", "utc_iso"]
