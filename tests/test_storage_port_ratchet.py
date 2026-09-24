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
while looking rigorous. The real number was 34, and it is now 0.
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

# Direct construction: 15 remain and they are legitimate. Each one opens a
# store to hand to `Agent`, or to list sessions — session and turn state stays
# on the local file under every backend, including `RemoteStore`, because it is
# per-conversation state no remote memory engine has a notion of. Porting them
# would mean widening `MemoryStore` with operations a remote backend could
# never implement. The ceiling stops the number growing; it is not a target of
# zero.
_MAX_DIRECT_CONSTRUCTION = 15

# Reach-through: **zero**, so this half is a ban rather than a ratchet. The
# replacements are `store.raw()` (a port that has a local file behind it) and
# `memory.store.local_connection(project)` (SQLite-specific work with no port
# involved). Both name what they are doing; `store._conn` named nothing.
_MAX_CONNECTION_REACH = 0


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


# Raw `sqlite3.connect(...)`: only `io_utils.open_sqlite` (every store opens its
# connection there), plus deliberate readers — `memory_query` (a `query_only`
# sandbox for agent SQL), the wiki FTS index (its own database file), and two
# read-only probes. A new raw connection to memory.db skips `busy_timeout`, so a
# write through it fails with "database is locked" the moment the daemon is
# writing — use `local_connection` or `open_sqlite`.
_RAW_CONNECT_ALLOWED = {
    "core/io_utils.py",
    "core/tools/builtin/memory_query.py",
    "modules/wiki/wiki.py",
    "core/doctor.py",
    "core/self_doc.py",
}


def test_no_new_raw_sqlite_connections() -> None:
    offenders = set()
    for rel, text in _iter_sources():
        for node in ast.walk(ast.parse(text)):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "connect"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "sqlite3"
            ):
                offenders.add(str(rel))
    assert offenders <= _RAW_CONNECT_ALLOWED, (
        f"raw sqlite3.connect in {sorted(offenders - _RAW_CONNECT_ALLOWED)}; "
        "open memory.db through `memory.store.local_connection(project)`"
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
    assert reach == _MAX_CONNECTION_REACH == 0, (
        "reach-through is at zero and stays there; if a legitimate case appears, "
        "it goes through `store.raw()` or `local_connection`, not through a "
        "raised ceiling"
    )
