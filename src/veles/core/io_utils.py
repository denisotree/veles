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

import json
import os
import tempfile
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")


def load_optional_json(path: Path, *, default: T | None = None) -> Any | T | None:
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
    """Write `data` as JSON to `path` via tmpfile + `os.replace` so a
    crash mid-write leaves the previous good file intact. Caller owns
    parent directory creation.

    `mode`, if given, is applied to the final file via `os.chmod` —
    useful for token files that need 0600."""
    body = json.dumps(data) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(body)
        os.replace(tmp_name, path)
    except Exception:
        # Best-effort cleanup if the tmpfile lingered.
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    if mode is not None:
        try:
            os.chmod(path, mode)
        except OSError:
            pass


__all__ = ["atomic_write_json", "load_optional_json"]
