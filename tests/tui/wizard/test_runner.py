"""WizardRunner sequencing — NEXT advances, BACK goes back, CANCEL raises."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from textual.app import App, ComposeResult

from veles.tui.wizard import WizardContext, WizardOutcome, WizardRunner
from veles.tui.wizard.runner import WizardCancelled


@dataclass
class _ScriptedStep:
    name: str
    title: str
    answer_key: str
    outcomes: list[WizardOutcome]  # one per visit (in order)
    visits: int = 0
    set_value: Any = "v"
    history: list[int] = field(default_factory=list)

    async def run(self, ctx: WizardContext) -> WizardOutcome:
        self.history.append(self.visits)
        outcome = self.outcomes[min(self.visits, len(self.outcomes) - 1)]
        self.visits += 1
        if outcome in (WizardOutcome.NEXT, WizardOutcome.SKIP):
            ctx.answers[self.answer_key] = self.set_value
        return outcome


class _Host(App):
    def compose(self) -> ComposeResult:
        return iter(())


async def _run(steps):
    app = _Host()
    async with app.run_test():
        runner = WizardRunner(app, steps)
        return await runner.run()


async def test_linear_next_collects_all_answers():
    s1 = _ScriptedStep("a", "A", "k_a", [WizardOutcome.NEXT], set_value=1)
    s2 = _ScriptedStep("b", "B", "k_b", [WizardOutcome.NEXT], set_value=2)
    s3 = _ScriptedStep("c", "C", "k_c", [WizardOutcome.NEXT], set_value=3)
    answers = await _run([s1, s2, s3])
    assert answers == {"k_a": 1, "k_b": 2, "k_c": 3}
    assert (s1.visits, s2.visits, s3.visits) == (1, 1, 1)


async def test_back_revisits_previous_step():
    s1 = _ScriptedStep(
        "a", "A", "k_a", [WizardOutcome.NEXT, WizardOutcome.NEXT], set_value="first"
    )
    s2 = _ScriptedStep("b", "B", "k_b", [WizardOutcome.BACK, WizardOutcome.NEXT])
    answers = await _run([s1, s2])
    # s1 must have been visited twice; s2 once with BACK, then forward.
    assert s1.visits == 2
    assert s2.visits == 2
    assert answers == {"k_a": "first", "k_b": "v"}


async def test_skip_advances_like_next():
    s1 = _ScriptedStep("a", "A", "k_a", [WizardOutcome.SKIP])
    s2 = _ScriptedStep("b", "B", "k_b", [WizardOutcome.NEXT])
    answers = await _run([s1, s2])
    # SKIP also sets the answer key in our scripted step (mirrors NEXT).
    assert "k_a" in answers and "k_b" in answers


async def test_cancel_raises_wizard_cancelled():
    s1 = _ScriptedStep("a", "A", "k_a", [WizardOutcome.CANCEL])
    s2 = _ScriptedStep("b", "B", "k_b", [WizardOutcome.NEXT])
    with pytest.raises(WizardCancelled):
        await _run([s1, s2])
    assert s2.visits == 0


async def test_back_at_first_step_is_a_noop():
    """BACK from step 0 holds the user there until they choose NEXT/CANCEL."""
    s1 = _ScriptedStep(
        "a", "A", "k_a", [WizardOutcome.BACK, WizardOutcome.BACK, WizardOutcome.NEXT]
    )
    s2 = _ScriptedStep("b", "B", "k_b", [WizardOutcome.NEXT])
    answers = await _run([s1, s2])
    assert s1.visits == 3
    assert s2.visits == 1
    assert answers == {"k_a": "v", "k_b": "v"}


async def test_initial_answers_carry_through():
    s1 = _ScriptedStep("a", "A", "k_a", [WizardOutcome.NEXT])
    answers = await _run([s1])
    # Re-run with initial supplied; the step still adds its own value but
    # the seed survives if untouched.
    app = _Host()
    async with app.run_test():
        runner = WizardRunner(app, [_ScriptedStep("b", "B", "k_b", [WizardOutcome.NEXT])])
        answers = await runner.run(initial={"prior": True})
    assert answers["prior"] is True
    assert answers["k_b"] == "v"
