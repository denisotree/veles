"""Wizard step protocol + shared types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from textual.app import App


class WizardOutcome(str, Enum):
    """Navigation signal returned by a step."""

    NEXT = "next"
    BACK = "back"
    SKIP = "skip"  # like NEXT but flag intent for telemetry / recap
    CANCEL = "cancel"


@dataclass
class WizardContext:
    """Mutable bag threaded through every step. `answers` accumulates
    user choices and is the wizard's return value. `app` lets a step
    push modal screens via the standard Textual API."""

    app: App
    answers: dict[str, Any] = field(default_factory=dict)


class WizardStep(Protocol):
    """One step in a wizard. Implementations push their own modal
    screen(s) and decide what to record in `ctx.answers` before
    returning a `WizardOutcome`."""

    name: str
    title: str

    async def run(self, ctx: WizardContext) -> WizardOutcome:
        ...


CANCEL_SENTINEL = "__wizard_cancel__"
"""Sentinel value our modal screens dismiss with when the user hits
Ctrl+Q to quit the whole wizard. Steps treat it as CANCEL; the runner
unwinds. Lives here (not in each step module) so a single string
constant doesn't drift between user_steps.py and project_steps.py."""


def outcome_from_dismiss(value: object) -> WizardOutcome | None:
    """Map a modal screen's dismiss value to a navigation outcome.

    Returns:
      `WizardOutcome.CANCEL` — user hit Ctrl+Q (raw sentinel, or a
        single-item list containing it — MultiSelectScreen wraps).
      `WizardOutcome.BACK` — Esc was pressed (dismiss value is None).
      `None` — value is a real answer; the caller continues processing.
    """
    if value == CANCEL_SENTINEL or value == [CANCEL_SENTINEL]:
        return WizardOutcome.CANCEL
    if value is None:
        return WizardOutcome.BACK
    return None


__all__ = [
    "CANCEL_SENTINEL",
    "WizardContext",
    "WizardOutcome",
    "WizardStep",
    "outcome_from_dismiss",
]
