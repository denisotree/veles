"""CI invariant: the storage escape hatches must shrink, never grow (M264).

**The defect this exists to catch.** M264 introduced `MemoryStore` so the
backend could be chosen in one place, and left two deliberate escape hatches
while the ~130 existing call sites move over: constructing `SessionStore`
directly, and reaching a raw `sqlite3.Connection` out of a store. Both are
documented as temporary.

Temporary is a claim about the future, and the future is where claims go to
die. The M252 lock exists because `record_use` was "obviously" going to be
wired up and then was not, for five months. The same shape applies here with a
worse ending: an escape hatch that quietly becomes the interface does not fail,
it just makes `RemoteStore` impossible again, silently, by accumulation.

So this is a **ratchet, not a ban**: the counts below are what existed when the
port landed, and they may only go down. The migration can land in as many
pieces as it needs; what it cannot do is grow a 134th site while nobody is
looking. Lowering a number here is the reward for porting a batch — do it in
the same commit, so the ceiling always reflects reality.
"""

from __future__ import annotations

import re
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src" / "veles"

# The port's own implementation is where both forms are legitimate: `SqliteStore`
# constructs the sync store, and `raw()` exists precisely to hand out the
# connection. Counting them would make the ratchet measure itself.
_EXEMPT = {
    Path("core/memory/store.py"),
    Path("core/memory/__init__.py"),
}

# Measured at the M264a commit (the planning figure of 43 counted definitions,
# annotations and the port's own file; the real call-site count is 32).
# Only ever revise downwards.
_MAX_DIRECT_CONSTRUCTION = 32
_MAX_CONNECTION_REACH = 90

_CONSTRUCTION = re.compile(r"\bSessionStore\(")
_REACH = re.compile(r"\.\s*_conn\b")


def _count(pattern: re.Pattern[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in _SRC.rglob("*.py"):
        rel = path.relative_to(_SRC)
        if rel in _EXEMPT:
            continue
        hits = len(pattern.findall(path.read_text(encoding="utf-8")))
        if hits:
            counts[str(rel)] = hits
    return counts


def test_direct_store_construction_does_not_grow() -> None:
    counts = _count(_CONSTRUCTION)
    total = sum(counts.values())
    assert total <= _MAX_DIRECT_CONSTRUCTION, (
        f"{total} direct SessionStore(...) constructions, ceiling is "
        f"{_MAX_DIRECT_CONSTRUCTION}. New code opens a store via "
        f"`memory.store.open_store(project)`.\n"
        + "\n".join(f"    {f}: {n}" for f, n in sorted(counts.items()))
    )


def test_connection_reach_through_does_not_grow() -> None:
    counts = _count(_REACH)
    total = sum(counts.values())
    assert total <= _MAX_CONNECTION_REACH, (
        f"{total} reach-throughs to a raw sqlite3 connection, ceiling is "
        f"{_MAX_CONNECTION_REACH}. A backend that is not SQLite has no such "
        f"connection: add the operation to `MemoryStore`, or go through "
        f"`SqliteStore.raw()` if it is genuinely SQLite-only.\n"
        + "\n".join(f"    {f}: {n}" for f, n in sorted(counts.items()))
    )


def test_ceilings_are_not_stale() -> None:
    """A ceiling far above reality stops being a ratchet. If a batch landed
    without lowering the numbers, this says so."""
    direct = sum(_count(_CONSTRUCTION).values())
    reach = sum(_count(_REACH).values())
    assert direct >= _MAX_DIRECT_CONSTRUCTION - 5, (
        f"only {direct} direct constructions remain against a ceiling of "
        f"{_MAX_DIRECT_CONSTRUCTION} — lower `_MAX_DIRECT_CONSTRUCTION` to {direct}"
    )
    assert reach >= _MAX_CONNECTION_REACH - 5, (
        f"only {reach} reach-throughs remain against a ceiling of "
        f"{_MAX_CONNECTION_REACH} — lower `_MAX_CONNECTION_REACH` to {reach}"
    )
