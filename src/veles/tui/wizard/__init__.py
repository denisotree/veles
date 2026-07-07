"""TUI wizard framework — sequence of modal screens replacing stdin prompts.

Public surface:
    WizardStep        — Protocol every step implements.
    WizardOutcome     — return type controlling navigation.
    WizardContext     — answers dict + app handle threaded through steps.
    WizardRunner      — orchestrates linear NEXT/BACK/CANCEL flow.

Reusable modal screens live under `tui.wizard.screens`.
"""

from veles.tui.wizard.runner import WizardRunner
from veles.tui.wizard.step import WizardContext, WizardOutcome, WizardStep

__all__ = ["WizardContext", "WizardOutcome", "WizardRunner", "WizardStep"]
