"""Yes/No confirmation."""

from __future__ import annotations

from typing import ClassVar

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Label, Static

from veles.tui.wizard.screens._base import WIZARD_CSS


class _FlatButton(Static, can_focus=True):
    """A focusable Label-style button: full styling control + simple
    Click / Enter / Space → emit Pressed.

    Replaces Textual's `Button` here because the framework's variant
    cascade (`Button.-primary { background: $primary }`) wins over
    our wizard-scoped overrides and the result is unreadable text on
    a solid colour."""

    DEFAULT_CSS = """
    _FlatButton {
        width: auto;
        min-width: 8;
        height: 1;
        padding: 0 2;
        margin: 0 1;
        background: $surface;
        color: $text;
        text-align: center;
        text-style: none;
    }
    _FlatButton:focus {
        background: $accent;
        color: $surface;
        text-style: bold;
    }
    _FlatButton:hover {
        background: $primary 20%;
    }
    """

    class Pressed(Message):
        def __init__(self, source: _FlatButton) -> None:
            super().__init__()
            self.source = source

    def __init__(self, label: str, *, id: str) -> None:  # noqa: A002
        super().__init__(label, id=id)
        self._label = label

    def on_click(self, event: events.Click) -> None:
        del event
        self.post_message(self.Pressed(self))


class ConfirmScreen(ModalScreen[bool | None]):
    """Returns True on Yes, False on No, None on Esc (BACK)."""

    DEFAULT_CSS = (
        WIZARD_CSS
        + """
    ConfirmScreen { align: center middle; }
    ConfirmScreen Horizontal { width: auto; height: auto; margin-top: 1; }
    """
    )

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "back", priority=True),
        Binding("y", "say_yes", "yes", priority=True),
        Binding("n", "say_no", "no", priority=True),
        Binding("left", "focus_yes", "← Yes", priority=True),
        Binding("right", "focus_no", "→ No", priority=True),
        Binding("enter", "confirm_focused", "confirm", priority=True),
        Binding("ctrl+q", "quit_wizard", "quit", priority=True),
    ]

    def __init__(
        self,
        title: str,
        question: str,
        *,
        default: bool = True,
        yes_label: str = "Yes",
        no_label: str = "No",
        hint: str = "Y/N · ←/→ or Tab to switch · Enter confirms · Esc back · Ctrl+Q quit",
    ) -> None:
        super().__init__()
        self._title = title
        self._question = question
        self._default = default
        self._yes_label = yes_label
        self._no_label = no_label
        self._hint = hint

    def compose(self) -> ComposeResult:
        with Vertical(classes="wizard-panel"):
            yield Label(self._title, classes="wizard-title")
            yield Label(self._question, classes="wizard-body")
            with Horizontal():
                yield _FlatButton(self._yes_label, id="wizard-yes")
                yield _FlatButton(self._no_label, id="wizard-no")
            yield Label(self._hint, classes="wizard-hint")

    def on_mount(self) -> None:
        target = "wizard-yes" if self._default else "wizard-no"
        self.query_one(f"#{target}", _FlatButton).focus()

    def on__flat_button_pressed(self, event: _FlatButton.Pressed) -> None:
        # Textual dispatches `_FlatButton.Pressed` as `on__flat_button_pressed`
        # (note double underscore because the class name starts with `_`).
        if event.source.id == "wizard-yes":
            self.dismiss(True)
        elif event.source.id == "wizard-no":
            self.dismiss(False)

    def action_say_yes(self) -> None:
        self.dismiss(True)

    def action_say_no(self) -> None:
        self.dismiss(False)

    def action_focus_yes(self) -> None:
        self.query_one("#wizard-yes", _FlatButton).focus()

    def action_focus_no(self) -> None:
        self.query_one("#wizard-no", _FlatButton).focus()

    def action_confirm_focused(self) -> None:
        """Enter on a focused Yes/No button — dismiss accordingly. Tab
        cycles focus natively; Enter here just observes which one ended
        up focused."""
        focused = self.focused
        if focused is None:
            self.dismiss(True)
            return
        if getattr(focused, "id", None) == "wizard-yes":
            self.dismiss(True)
        elif getattr(focused, "id", None) == "wizard-no":
            self.dismiss(False)
        else:
            self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_quit_wizard(self) -> None:
        self.dismiss("__wizard_cancel__")  # type: ignore[arg-type]
