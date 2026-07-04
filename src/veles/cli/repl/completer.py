"""Tab-completion plumbing.

A `Completer` produces zero or more full-line completion candidates
based on the current composer text and cursor position. The Composer
caches the candidate list on the first Tab press and cycles through it
on repeated presses — fast and predictable, no ghost-text UI required.

Phase 4 ships `SlashCompleter`. Phase 5 will add `PathCompleter` (for
`/wiki read`) and `SessionIdCompleter` (for `/load`). The dispatcher
below composes them: when the active line is a slash command, the
slash completer fires first; if the command word is complete and the
cursor is in argument territory, an argument-specific completer takes
over.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from veles.cli.repl.slash import SlashRegistry


@runtime_checkable
class Completer(Protocol):
    def candidates(self, text: str, cursor: int) -> list[str]:
        """Return possible full-line replacements. The Composer assigns
        each one verbatim to `self.text` when cycling."""
        ...


class SlashCompleter:
    """Complete the leading `/command` token from the registry's names.

    Triggered only when the current line begins with `/` and the cursor
    sits inside the command word itself (no spaces to its left yet).
    Once the user has typed a space — i.e. moved into arguments — the
    slash completer steps aside.
    """

    def __init__(self, registry: SlashRegistry) -> None:
        self._registry = registry

    def candidates(self, text: str, cursor: int) -> list[str]:
        before = text[:cursor]
        after = text[cursor:]
        if not before.startswith("/"):
            return []
        # If anything past the first whitespace is to the left of cursor,
        # we're in argument-completion territory — out of scope here.
        first_space = before.find(" ")
        if first_space != -1:
            return []
        prefix = before
        names = self._registry.names()
        matches = sorted(n for n in names if n.startswith(prefix))
        # Cycle order: present canonical names first, then aliases. The
        # registry's `names()` already merges both; sort is alphabetical
        # which is the most predictable order for users.
        return [m + after for m in matches]


class NullCompleter:
    """No-op completer. Used when the Composer is instantiated without
    a registry (some unit tests, future plugin scenarios)."""

    def candidates(self, text: str, cursor: int) -> list[str]:
        del text, cursor
        return []
