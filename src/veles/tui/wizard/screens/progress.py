"""Final recap / progress-indicator screen.

Displays a bullet list of "what was done" with optional auto-dismiss
on any key. Pure informational — there's no semantic "back" from a
recap, so Esc just closes it."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label

from veles.tui.wizard.screens._base import WIZARD_CSS


class ProgressScreen(ModalScreen[None]):
    """Show a recap; any key closes it."""

    DEFAULT_CSS = (
        WIZARD_CSS
        + """
    ProgressScreen { align: center middle; }
    ProgressScreen .recap-line {
        margin: 0;
    }
    """
    )

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("enter", "close", "close", priority=True),
        Binding("escape", "close", "close", priority=True),
        Binding("space", "close", "close", priority=True),
    ]

    def __init__(
        self,
        title: str,
        lines: list[str],
        *,
        hint: str = "Press Enter to continue",
    ) -> None:
        super().__init__()
        self._title = title
        self._lines = lines
        self._hint = hint

    def compose(self) -> ComposeResult:
        with Vertical(classes="wizard-panel"):
            yield Label(self._title, classes="wizard-title")
            for line in self._lines:
                yield Label(line, classes="recap-line")
            yield Label(self._hint, classes="wizard-hint")

    def action_close(self) -> None:
        self.dismiss(None)
