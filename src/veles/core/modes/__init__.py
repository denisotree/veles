"""Per-turn execution modes for the TUI agent loop.

Each mode is a Strategy that wraps the full work of one user prompt:
it may invoke `Agent.run` zero, one, or many times, post intermediate
chat lines, and ends by posting a single `TurnDone` message.

The bridge dispatches to `MODES[state.mode].run_turn(prompt, ctx)`;
modes never touch Textual directly — they use the `post` callback on
`ModeContext`.

Phase 1 only ships WritingMode; PlanningMode, AutoMode, GoalMode land
in subsequent phases. All four names are reserved in `ModeName` and
default to WritingMode behaviour until their phase lands, so the UI
chip + cycle work end-to-end from Phase 2 onwards.
"""

from __future__ import annotations

from typing import Literal

from veles.core.modes.auto import AutoMode
from veles.core.modes.base import Mode, ModeContext
from veles.core.modes.goal import GoalMode
from veles.core.modes.planning import PlanningMode
from veles.core.modes.writing import WritingMode

ModeName = Literal["auto", "planning", "writing", "goal"]

# Cycle order for Shift+Tab. `auto` is the default first stop because
# it's the smartest fallback when the user hasn't expressed intent.
CYCLE_ORDER: tuple[ModeName, ...] = ("auto", "planning", "writing", "goal")

# Single instance per mode — they're stateless Strategy objects.
_WRITING = WritingMode()
_PLANNING = PlanningMode()
_AUTO = AutoMode()
_GOAL = GoalMode()

MODES: dict[ModeName, Mode] = {
    "auto": _AUTO,
    "planning": _PLANNING,
    "writing": _WRITING,
    "goal": _GOAL,
}


def get_mode(name: str) -> Mode:
    """Return the Mode for `name`, falling back to WritingMode for any
    unknown / corrupt value. Callers (persistence loader, /mode slash)
    can trust this never raises."""
    if name in MODES:
        return MODES[name]  # type: ignore[index]
    return _WRITING


def next_mode(current: str) -> ModeName:
    """Next mode in the cycle. Unknown current → first entry."""
    try:
        idx = CYCLE_ORDER.index(current)  # type: ignore[arg-type]
    except ValueError:
        return CYCLE_ORDER[0]
    return CYCLE_ORDER[(idx + 1) % len(CYCLE_ORDER)]


__all__ = [
    "CYCLE_ORDER",
    "MODES",
    "AutoMode",
    "GoalMode",
    "Mode",
    "ModeContext",
    "ModeName",
    "PlanningMode",
    "WritingMode",
    "get_mode",
    "next_mode",
]
