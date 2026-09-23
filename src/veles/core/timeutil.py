"""The one timestamp format Veles writes into its state files and logs."""

from __future__ import annotations

import time


def utc_iso(ts: float | None = None) -> str:
    """`2026-09-23T10:00:00Z` for `ts` (seconds since the epoch), or for now."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


__all__ = ["utc_iso"]
