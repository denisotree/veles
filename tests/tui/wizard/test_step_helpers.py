"""M-R1.7: centralised wizard navigation helpers."""

from __future__ import annotations

from veles.tui.wizard.step import (
    CANCEL_SENTINEL,
    WizardOutcome,
    outcome_from_dismiss,
)


def test_cancel_sentinel_is_stable_string() -> None:
    """Tests + production code both refer to this literal — pinning
    avoids drift if someone renames it."""
    assert CANCEL_SENTINEL == "__wizard_cancel__"


def test_cancel_scalar() -> None:
    assert outcome_from_dismiss(CANCEL_SENTINEL) is WizardOutcome.CANCEL


def test_cancel_in_list_form() -> None:
    """MultiSelectScreen wraps the dismiss value into a list when the
    user cancels mid-multi-select. The helper must handle both shapes."""
    assert outcome_from_dismiss([CANCEL_SENTINEL]) is WizardOutcome.CANCEL


def test_none_means_back() -> None:
    assert outcome_from_dismiss(None) is WizardOutcome.BACK


def test_real_answer_returns_none() -> None:
    """Caller continues processing only when the helper returns None."""
    assert outcome_from_dismiss("en") is None
    assert outcome_from_dismiss(True) is None
    assert outcome_from_dismiss(["a", "b"]) is None
