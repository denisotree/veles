"""Linear wizard orchestrator.

Drives steps in order, honouring NEXT/BACK/SKIP/CANCEL. Steps own their
own modal screens; the runner only schedules them and threads the
shared `WizardContext`. Idempotent: a step's previous answer (if any)
is left in `ctx.answers` so it can default the next presentation when
the user navigates BACK.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from veles.tui.wizard.step import WizardContext, WizardOutcome, WizardStep

if TYPE_CHECKING:
    from textual.app import App


class WizardCancelled(RuntimeError):
    """Raised when the user cancels mid-flow."""


class WizardRunner:
    """Run `steps` sequentially. Returns the final answers dict on NEXT
    past the last step, or raises `WizardCancelled` if any step returns
    CANCEL."""

    def __init__(self, app: App, steps: list[WizardStep]) -> None:
        self._app = app
        self._steps = list(steps)

    @property
    def steps(self) -> list[WizardStep]:
        return list(self._steps)

    async def run(self, *, initial: dict | None = None) -> dict:
        ctx = WizardContext(app=self._app, answers=dict(initial or {}))
        idx = 0
        while 0 <= idx < len(self._steps):
            step = self._steps[idx]
            outcome = await step.run(ctx)
            if outcome is WizardOutcome.CANCEL:
                raise WizardCancelled(f"cancelled at step {step.name!r}")
            if outcome is WizardOutcome.BACK:
                idx = max(0, idx - 1)
                continue
            # NEXT and SKIP both advance.
            idx += 1
        return ctx.answers


__all__ = ["WizardCancelled", "WizardRunner"]
