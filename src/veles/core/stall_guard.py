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
    """Trips once when the loop stops making progress. Two signals:

    - `repeat_limit`: the SAME whole-round signature repeats this many times
      (the classic "same dead tool call every round" stall).
    - `call_repeat_limit`: a single `(tool, args)` call recurs this many times
      across the turn, even when paired with different other calls each round.
      Catches a confused agent re-reading the same file over and over (the
      observed 4M-token migration runaway) — the round signature keeps changing,
      so the round guard alone never fires.

    Either limit set to 0/None disables that signal; both disabled = inert."""

    __slots__ = ("_call_counts", "_call_repeat_limit", "_counts", "_repeat_limit", "_tripped")

    def __init__(self, *, repeat_limit: int | None = 3, call_repeat_limit: int | None = 7) -> None:
        self._repeat_limit = repeat_limit if repeat_limit and repeat_limit > 0 else None
        self._call_repeat_limit = (
            call_repeat_limit if call_repeat_limit and call_repeat_limit > 0 else None
        )
        self._counts: Counter[str] = Counter()
        self._call_counts: Counter[str] = Counter()
        self._tripped = False

    def record(self, tool_calls: Sequence[ToolCall]) -> bool:
        """Record one round's tool calls. Returns True exactly once — on the
        round that first trips either signal — so the caller forces a single
        tool-free answer round. Returns False thereafter (and always, when
        disabled or given no tool calls)."""
        if self._tripped or not tool_calls:
            return False
        # Signal 1: the whole round repeats verbatim.
        if self._repeat_limit is not None:
            sig = signature(tool_calls)
            if sig:
                self._counts[sig] += 1
                if self._counts[sig] >= self._repeat_limit:
                    self._tripped = True
                    return True
        # Signal 2: a single call recurs across the turn (re-reading the same
        # file), regardless of what else the round contains.
        if self._call_repeat_limit is not None:
            for call in tool_calls:
                csig = signature([call])
                if not csig:
                    continue
                self._call_counts[csig] += 1
                if self._call_counts[csig] >= self._call_repeat_limit:
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

# Soft, one-time heads-up when a turn has burned a lot of tokens. Unlike
# STALL_NUDGE it does NOT withhold tools — a genuinely progressing long job keeps
# going; a looping one is told to stop. `{tokens}` is filled with the running total.
TOKEN_WARN_NUDGE = (
    "You have already used {tokens} tokens this turn. If you are repeating work "
    "or looping without making progress, stop now and give the best answer you "
    "can from what you have. Keep going only if you are genuinely making progress."
)
