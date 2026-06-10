"""Sanitization rules — atomic units that rewrite a piece of text.

Two concrete shapes cover everything Veles needs today:

- `LiteralRule` — plain `str.replace`. Cheap; used for fixed strings
  whose value is known at runtime (project root, $HOME, OS user).
- `RegexRule` — compiled-once `re.sub`. Used for known secret formats
  (API keys, bearer tokens) and any user-defined patterns from TOML.

A `RuleSet` applies rules in registration order. Order matters when a
later rule could match the replacement text of an earlier one — keep
specific rules first. Built-in ordering is fixed in `builtin.py`.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Iterable, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class Rule(Protocol):
    """A single rewrite step. Implementations must be pure and idempotent
    on their own output: `rule.apply(rule.apply(t)) == rule.apply(t)`.

    Idempotence holds automatically when `replacement` does not contain
    `pattern` — the built-in rules respect this. User-supplied rules
    via TOML are best-effort; a non-idempotent rule will rewrite on
    every pass but won't corrupt data."""

    name: str

    def apply(self, text: str) -> str: ...


@dataclass(frozen=True)
class LiteralRule:
    """`str.replace(pattern, replacement)`."""

    name: str
    pattern: str
    replacement: str

    def apply(self, text: str) -> str:
        if not text or not self.pattern:
            return text
        return text.replace(self.pattern, self.replacement)


@dataclass(frozen=True)
class RegexRule:
    """`re.sub(pattern, replacement, text)` with a precompiled pattern."""

    name: str
    pattern: str
    replacement: str
    _compiled: re.Pattern[str]

    @classmethod
    def build(cls, name: str, pattern: str, replacement: str) -> "RegexRule | None":
        """Compile up-front; return None and log on bad pattern instead
        of letting the broken rule crash the sanitize call."""
        try:
            compiled = re.compile(pattern)
        except re.error as exc:
            logger.warning(
                "sanitize: skipping rule %r — invalid regex %r: %s",
                name,
                pattern,
                exc,
            )
            return None
        return cls(name=name, pattern=pattern, replacement=replacement, _compiled=compiled)

    def apply(self, text: str) -> str:
        if not text:
            return text
        return self._compiled.sub(self.replacement, text)


class RuleSet:
    """Ordered collection of rules. Applies each in turn."""

    __slots__ = ("_rules",)

    def __init__(self, rules: Iterable[Rule]) -> None:
        self._rules = tuple(rules)

    def __len__(self) -> int:
        return len(self._rules)

    def __iter__(self):
        return iter(self._rules)

    def apply(self, text: str) -> str:
        if not text:
            return text
        out = text
        for rule in self._rules:
            out = rule.apply(out)
        return out
