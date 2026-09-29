"""Tiny version comparison for `requires_veles` — dotted integers, comma-joined clauses.

Deliberately not `packaging`: it is not a runtime dependency, and extensions only
need `>=, >, <=, <, ==, !=` over MAJOR.MINOR.PATCH.
"""

from __future__ import annotations

import re
from itertools import zip_longest

_OPS = (">=", "<=", "==", "!=", ">", "<")


def parse_version(text: str) -> tuple[int, ...]:
    core = re.split(r"[+-]", text.strip(), maxsplit=1)[0]
    parts = core.split(".")
    if not core or not all(p.isdigit() for p in parts):
        raise ValueError(f"not a dotted version: {text!r}")
    return tuple(int(p) for p in parts)


def _compare(a: tuple[int, ...], b: tuple[int, ...]) -> int:
    for x, y in zip_longest(a, b, fillvalue=0):
        if x != y:
            return 1 if x > y else -1
    return 0


def satisfies(version: str, spec: str) -> bool:
    """True when `version` meets every clause of `spec` (e.g. ">=1.0,<2")."""
    current = parse_version(version)
    for clause in (c.strip() for c in spec.split(",")):
        if not clause:
            continue
        op = next((o for o in _OPS if clause.startswith(o)), None)
        if op is None:
            raise ValueError(f"unsupported version clause {clause!r}")
        c = _compare(current, parse_version(clause[len(op) :]))
        ok = {
            ">=": c >= 0,
            "<=": c <= 0,
            "==": c == 0,
            "!=": c != 0,
            ">": c > 0,
            "<": c < 0,
        }[op]
        if not ok:
            return False
    return True


def is_newer(a: str, b: str) -> bool:
    return _compare(parse_version(a), parse_version(b)) > 0
