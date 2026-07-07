"""Single-line text input with optional password masking."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label

from veles.tui.wizard.screens._base import WIZARD_CSS


class InputScreen(ModalScreen[str | None]):
    """Returns the entered text, or None on Esc (BACK)."""

    DEFAULT_CSS = (
        WIZARD_CSS
        + """
    InputScreen { align: center middle; }
    InputScreen Input { margin-top: 1; }
    """
    )

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "back", priority=True),
        Binding("ctrl+q", "quit_wizard", "quit", priority=True),
    ]

    def __init__(
        self,
        title: str,
        *,
        prompt: str = "",
        default: str = "",
        placeholder: str = "",
        password: bool = False,
        hint: str = "Enter confirms · Esc back · Ctrl+Q quit",
    ) -> None:
        super().__init__()
        self._title = title
        self._prompt = prompt
        self._default = default
        self._placeholder = placeholder
        self._password = password
        self._hint = hint

    def compose(self) -> ComposeResult:
        with Vertical(classes="wizard-panel"):
            yield Label(self._title, classes="wizard-title")
            if self._prompt:
                yield Label(self._prompt, classes="wizard-subtitle")
            self._input = Input(
                value=self._default,
                placeholder=self._placeholder,
                password=self._password,
                id="wizard-input",
            )
            yield self._input
            yield Label(self._hint, classes="wizard-hint")

    def on_mount(self) -> None:
        self._input.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        del event
        self.dismiss(self._input.value)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_quit_wizard(self) -> None:
        self.dismiss("__wizard_cancel__")
