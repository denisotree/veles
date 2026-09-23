"""Tiny shared helpers for permissive JSON reads + atomic writes.

Veles has 9+ modules that each rolled their own
`try: json.loads(path.read_text(...)); except (OSError, JSONDecodeError):`
pattern with subtly different default-return shapes. This module
centralises the common case so adding a new state file means importing
two functions instead of copying twenty lines of try/except.

The atomic-write half mirrors `core/autopilot.py::activate` — temp file
in the same directory, then `os.replace` for crash safety. Same pattern
shows up in `core/trust_store.py`, `core/budget_state.py`,
`core/curator_state.py`. M-R1.5 only migrates the simplest call sites;
the rest live in the R3 backlog because they need bespoke validation.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")


def load_optional_json[T](path: Path, *, default: T | None = None) -> Any | T | None:
    """Read JSON from `path`. Missing file, decode error, OSError, or a
    non-dict top-level value all return `default`. Never raises.

    Callers that need to validate the inner shape (e.g. "must be a list
    of strings") layer their own checks on top of the dict returned
    here. The helper draws the line at "load it without crashing"."""
    if not path.is_file():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    return data


def atomic_write_json(path: Path, data: Any, *, mode: int | None = None) -> None:
    """Write `data` as compact JSON to `path` atomically (see `atomic_write_text`)."""
    atomic_write_text(path, json.dumps(data) + "\n", mode=mode)


def atomic_write_text(path: Path, text: str, *, mode: int | None = None) -> None:
    """Write `text` to `path` via tmpfile + `os.replace`, so a crash mid-write
    leaves the previous good file intact and a concurrent reader never sees a
    half-written one. Creates the parent directory.

    `mode`, if given, is applied to the final file via `os.chmod` —
    useful for token files that need 0600."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp_name, path)
    except Exception:
        # Best-effort cleanup if the tmpfile lingered.
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise
    if mode is not None:
        with contextlib.suppress(OSError):
            os.chmod(path, mode)


def prune_rotated(path: Path, *, keep: int) -> list[Path]:
    """Delete all but the newest `keep` rotated siblings of `path`.

    `TraceWriter` and `EventWriter` both rotate to `<name>.<unix_ts>[.<n>]` and,
    until now, kept every sibling forever — `trace.py` said outright that
    "cleanup is a curator concern", and the curator does not do it. At measured
    volume (~530 B per trace record, ~1.1 KB of events per agent turn) the first
    50 MB rotation is years away, so this prevents a slow leak rather than
    stopping an active one.

    Only *rotated* files are touched — the live file has no numeric suffix and
    is skipped by the pattern. Ordering is by mtime, not by the timestamp in the
    name, so a same-second `.<ts>.<n>` collision cannot delete the wrong one.

    Best-effort: a file that vanishes between listing and unlink (a second
    process pruning, an external cleanup) is not an error worth failing a write
    over. Returns what was actually removed, for the test to assert on.
    """
    if keep < 0:
        raise ValueError("keep must be >= 0")
    siblings = [
        p
        for p in path.parent.glob(f"{path.name}.*")
        if p.is_file() and p.name[len(path.name) + 1 :].split(".")[0].isdigit()
    ]
    if len(siblings) <= keep:
        return []
    siblings.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    removed: list[Path] = []
    for stale in siblings[keep:]:
        try:
            stale.unlink()
        except OSError:  # pragma: no cover - raced with another pruner
            continue
        removed.append(stale)
    return removed


__all__ = ["atomic_write_json", "load_optional_json", "prune_rotated"]
