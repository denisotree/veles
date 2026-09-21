"""CI invariant: the storage escape hatches must shrink, never grow (M264).

**The defect this exists to catch.** M264 introduced `MemoryStore` so the
backend could be chosen in one place, and left two deliberate escape hatches
while the existing call sites move over: constructing `SessionStore` directly,
and reaching a raw `sqlite3.Connection` out of someone else's store. Both are
documented as temporary.

Temporary is a claim about the future, and the future is where claims go to
die. The M252 lock exists because `record_use` was "obviously" going to be
wired up and then was not, for five months. The same shape applies here with a
worse ending: an escape hatch that quietly becomes the interface does not fail,
it just makes another backend impossible again, silently, by accumulation.

So this is a **ratchet, not a ban**: the counts below are what exists now, and
they may only go down. The migration can land in as many pieces as it needs;
what it cannot do is grow one more site while nobody is looking. Lowering a
number here is the reward for porting a batch — do it in the same commit, so
the ceiling always reflects reality.

**Counted by AST, not by grep.** The first cut of this file matched `._conn`
textually and reported 90 sites. Most of those were `self._conn` inside
`JobsStore`, `TasksStore` and `RuntimeSessionStore` — sibling stores that share
the project's database file and legitimately own their own connection. They are
not port violations, and counting them made the ratchet measure the wrong thing
while looking rigorous. The real number was 34.
"""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src" / "veles"

# The port's own implementation is where both forms are legitimate: `SqliteStore`
# constructs the sync store, and `raw()` exists precisely to hand out the
# connection. Counting them would make the ratchet measure itself.
_EXEMPT = {Path("core/memory/store.py"), Path("core/memory/__init__.py")}

# Measured at the M264c commit. Only ever revise downwards.
_MAX_DIRECT_CONSTRUCTION = 28
_MAX_CONNECTION_REACH = 22


def _iter_sources() -> list[tuple[Path, str]]:
    out = []
    for path in _SRC.rglob("*.py"):
        if path.relative_to(_SRC) in _EXEMPT:
            continue
        out.append((path.relative_to(_SRC), path.read_text(encoding="utf-8")))
    return out


def _count_constructions() -> Counter[str]:
    counts: Counter[str] = Counter()
    for rel, text in _iter_sources():
        for node in ast.walk(ast.parse(text)):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "SessionStore"
            ):
                counts[str(rel)] += 1
    return counts


def _count_reach_throughs() -> Counter[str]:
    """`x._conn` where `x` is not `self` — i.e. code reaching into a connection
    it does not own. A store touching its own `self._conn` is not a violation;
    it is a store."""
    counts: Counter[str] = Counter()
    for rel, text in _iter_sources():
        for node in ast.walk(ast.parse(text)):
            if not (isinstance(node, ast.Attribute) and node.attr == "_conn"):
                continue
            if isinstance(node.value, ast.Name) and node.value.id == "self":
                continue
            counts[str(rel)] += 1
    return counts


def _report(counts: Counter[str]) -> str:
    return "\n".join(f"    {f}: {n}" for f, n in sorted(counts.items()))


def test_direct_store_construction_does_not_grow() -> None:
    counts = _count_constructions()
    total = sum(counts.values())
    assert total <= _MAX_DIRECT_CONSTRUCTION, (
        f"{total} direct SessionStore(...) constructions, ceiling is "
        f"{_MAX_DIRECT_CONSTRUCTION}. New code opens a store via "
        f"`memory.store.open_store(project)`.\n" + _report(counts)
    )


def test_connection_reach_through_does_not_grow() -> None:
    counts = _count_reach_throughs()
    total = sum(counts.values())
    assert total <= _MAX_CONNECTION_REACH, (
        f"{total} reach-throughs into a connection the caller does not own, "
        f"ceiling is {_MAX_CONNECTION_REACH}. Use `store.raw()`, which says in "
        f"its name that the work is SQLite-specific, or add the operation to "
        f"`MemoryStore` if a remote backend could serve it.\n" + _report(counts)
    )


def test_ceilings_are_not_stale() -> None:
    """A ceiling far above reality stops being a ratchet. If a batch landed
    without lowering the numbers, this says so."""
    direct = sum(_count_constructions().values())
    reach = sum(_count_reach_throughs().values())
    assert direct >= _MAX_DIRECT_CONSTRUCTION - 4, (
        f"only {direct} direct constructions remain against a ceiling of "
        f"{_MAX_DIRECT_CONSTRUCTION} — lower `_MAX_DIRECT_CONSTRUCTION` to {direct}"
    )
    assert reach >= _MAX_CONNECTION_REACH - 4, (
        f"only {reach} reach-throughs remain against a ceiling of "
        f"{_MAX_CONNECTION_REACH} — lower `_MAX_CONNECTION_REACH` to {reach}"
    )
