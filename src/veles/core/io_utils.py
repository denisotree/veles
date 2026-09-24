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
import logging
import os
import sqlite3
import tempfile
import time
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")
logger = logging.getLogger(__name__)


def load_optional_toml(path: Path) -> dict[str, Any]:
    """Parse a TOML file; missing, unreadable or malformed → `{}`. Never raises.

    A malformed file is logged: somebody edited it and wants to know why their
    change had no effect."""
    if not path.is_file():
        return {}
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        logger.warning("%s ignored: %s", path, exc)
        return {}


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


def read_fresh_json(path: Path, *, max_age_s: float) -> dict[str, Any] | None:
    """A cache file written by `write_stamped_json`, or None when it is missing,
    corrupt, or older than `max_age_s`. Never raises — a bad cache is a miss."""
    data = load_optional_json(path)
    if not isinstance(data, dict):
        return None
    try:
        fetched_at = datetime.fromisoformat(data["fetched_at"])
    except (KeyError, TypeError, ValueError):
        return None
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=UTC)
    if (datetime.now(UTC) - fetched_at).total_seconds() >= max_age_s:
        return None
    return data


def write_stamped_json(path: Path, data: dict[str, Any]) -> None:
    """Atomically write `data` plus a `fetched_at` stamp for `read_fresh_json`."""
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    atomic_write_json(path, {**data, "fetched_at": stamp})


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
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        tmp.replace(path)
    except Exception:
        # Best-effort cleanup if the tmpfile lingered.
        tmp.unlink(missing_ok=True)
        raise
    if mode is not None:
        with contextlib.suppress(OSError):
            path.chmod(mode)


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


class RotatingJsonl:
    """Append JSON objects to a JSONL file with size-bounded rotation.

    When the next line would push the file past `max_bytes`, it is renamed to
    `<name>.<unix_ts>` (plus a counter if two rotations land in one second) and
    all but the newest `keep_rotated` siblings are deleted (`0` keeps them all).
    Write errors propagate — the caller decides whether a broken log may stop it.
    """

    def __init__(self, path: Path, *, max_bytes: int, keep_rotated: int) -> None:
        self._path = path
        self._max_bytes = max_bytes
        self._keep_rotated = keep_rotated
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def append(self, obj: Any) -> None:
        data = (json.dumps(obj, separators=(",", ":")) + "\n").encode("utf-8")
        if self._path.exists() and self._path.stat().st_size + len(data) > self._max_bytes:
            self._rotate()
        with self._path.open("ab") as f:
            f.write(data)

    def _rotate(self) -> None:
        ts = int(time.time())
        target = self._path.with_name(f"{self._path.name}.{ts}")
        n = 1
        while target.exists():
            target = self._path.with_name(f"{self._path.name}.{ts}.{n}")
            n += 1
        self._path.replace(target)
        prune_rotated(self._path, keep=self._keep_rotated)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Every JSON line of `path`; blank and malformed lines are skipped (a crash
    mid-write must not poison the whole file). Missing file → `[]`."""
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def open_sqlite(db_path: Path | str) -> sqlite3.Connection:
    """Open a project SQLite file the way every store needs it.

    Autocommit (`isolation_level=None`, group writes with an explicit BEGIN),
    shareable across threads, `sqlite3.Row` rows, foreign keys on; for a file,
    WAL plus a 5 s busy timeout — the CLI and the daemon write the same
    memory.db, and SQLite's default timeout of 0 turns every overlap into an
    immediate "database is locked". `":memory:"` works for tests."""
    target = str(db_path)
    if target != ":memory:":
        Path(target).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if target != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def dump_toml(data: dict[str, Any]) -> str:
    """Emit nested tables to TOML at arbitrary depth; string / bool / int / float /
    list-of-scalars values. The one TOML writer (stdlib `tomllib` only reads).

    Scalar keys are emitted *before* sub-table headers (TOML requires a table's
    own keys to precede its `[parent.child]` headers, else they'd bind to the
    wrong table). A parent header is skipped when it carries only sub-tables and
    no scalars — so `{routing: {tasks: {…}}}` emits a clean `[routing.tasks]`
    without a stray empty `[routing]`."""
    lines: list[str] = []
    _emit_table(data, (), lines)
    return "\n".join(lines).strip() + "\n"


def _emit_table(table: dict[str, Any], prefix: tuple[str, ...], lines: list[str]) -> None:
    scalars = {k: v for k, v in table.items() if not isinstance(v, dict)}
    subtables = {k: v for k, v in table.items() if isinstance(v, dict)}
    if prefix:
        # Emit this table's header when it has scalar keys, or when it has no
        # sub-tables at all (preserve a genuinely empty `[section]`).
        if scalars or not subtables:
            lines.append(f"[{'.'.join(prefix)}]")
            for k, v in scalars.items():
                lines.append(f"{k} = {_emit_value(v)}")
            lines.append("")
    else:
        # Root-level scalars (rare) are emitted bare, before any section.
        for k, v in scalars.items():
            lines.append(f"{k} = {_emit_value(v)}")
    for sub_key, sub_val in subtables.items():
        _emit_table(sub_val, (*prefix, sub_key), lines)


def _emit_value(v: Any) -> str:
    if isinstance(v, list):
        return "[" + ", ".join(_emit_value(item) for item in v) + "]"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        escaped = v.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return str(v)


__all__ = [
    "RotatingJsonl",
    "atomic_write_json",
    "atomic_write_text",
    "dump_toml",
    "load_optional_json",
    "load_optional_toml",
    "open_sqlite",
    "prune_rotated",
    "read_fresh_json",
    "read_jsonl",
    "write_stamped_json",
]
