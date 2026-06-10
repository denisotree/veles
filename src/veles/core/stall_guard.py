"""M144: stall/loop guard for the agent turn-loop.

Veles' loop terminates the moment the model returns no tool calls, so the
"intent without action" stall (model narrates "let me check X" and keeps
looping) that some agent frameworks must guard against cannot occur here — that
case simply ends the turn. The Veles-specific failure mode is a model that
calls the *same tool with the same arguments* round after round, making no
progress while burning iterations and token budget.

`StallGuard` watches the per-round tool-call signature and trips when one
signature recurs `repeat_limit` times within a single turn. The agent reacts
by forcing one tool-free round (provider called with `tools=None`) so the
model must answer with what it has instead of calling the same dead tool
again. Self-contained and cheap: a `Counter` of short signatures, no I/O.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from veles.core.provider import ToolCall

# Per-argument-blob cap so a signature stays a cheap, bounded key while still
# distinguishing genuinely different calls (different paths, different shells).
_ARG_SIG_CHARS = 120


def signature(tool_calls: Sequence[ToolCall]) -> str:
    """Deterministic, bounded key for one round's tool calls. Arguments are
    sorted so dict ordering can't make two identical calls look different."""
    parts: list[str] = []
    for call in tool_calls:
        try:
            items = sorted(call.arguments.items())
        except AttributeError:  # arguments not a mapping — fall back to repr
            items = call.arguments  # type: ignore[assignment]
        blob = repr(items)[:_ARG_SIG_CHARS]
        parts.append(f"{call.name}:{blob}")
    return "|".join(parts)


class StallGuard:
    """Trips once when a tool-call signature repeats `repeat_limit` times in a
    turn. `repeat_limit` of 0 or None disables the guard entirely."""

    __slots__ = ("_repeat_limit", "_counts", "_tripped")

    def __init__(self, *, repeat_limit: int | None = 3) -> None:
        self._repeat_limit = repeat_limit if repeat_limit and repeat_limit > 0 else None
        self._counts: Counter[str] = Counter()
        self._tripped = False

    def record(self, tool_calls: Sequence[ToolCall]) -> bool:
        """Record one round's tool calls. Returns True exactly once — on the
        round that first reaches `repeat_limit` repeats of any signature — so
        the caller forces a single tool-free answer round. Returns False
        thereafter (and always, when disabled or given no tool calls)."""
        if self._repeat_limit is None or self._tripped or not tool_calls:
            return False
        sig = signature(tool_calls)
        if not sig:
            return False
        self._counts[sig] += 1
        if self._counts[sig] >= self._repeat_limit:
            self._tripped = True
            return True
        return False

    @property
    def tripped(self) -> bool:
        return self._tripped


# Injected as a user-role nudge after the stalling round's tool results, right
# before the forced tool-free round. Kept short and directive.
STALL_NUDGE = (
    "You have repeated the same tool call several times without making "
    "progress. Stop calling tools now and reply with the best answer you can "
    "give from what you already have — or, if you are blocked, explain exactly "
    "what is preventing progress and what you would need to continue."
)
