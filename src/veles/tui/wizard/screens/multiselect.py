"""Select multiple items from a list, plus optional free-text additions.

Used by e.g. Telegram whitelist where the user wants to enter usernames
that aren't in any pre-canned list. Items can be toggled with Space;
Enter confirms the current selection set."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, ListItem, ListView

from veles.tui.wizard.screens._base import WIZARD_CSS


@dataclass(slots=True)
class _Row:
    label: str
    value: str
    selected: bool = False


class MultiSelectScreen(ModalScreen[list[str] | None]):
    """Returns the picked `value` list, or None on Esc."""

    DEFAULT_CSS = (
        WIZARD_CSS
        + """
    MultiSelectScreen { align: center middle; }
    MultiSelectScreen ListView { height: auto; max-height: 12; }
    MultiSelectScreen Input { margin-top: 1; }
    """
    )

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "back", priority=True),
        Binding("space", "toggle", "toggle", priority=True),
        Binding("ctrl+s", "submit", "submit", priority=True),
        Binding("ctrl+q", "quit_wizard", "quit", priority=True),
    ]

    def __init__(
        self,
        title: str,
        items: list[tuple[str, str]],
        *,
        allow_freeform: bool = False,
        freeform_placeholder: str = "",
        preselected: list[str] | None = None,
        hint: str = "Space toggle · Ctrl+S submit · Esc back · Ctrl+Q quit",
    ) -> None:
        super().__init__()
        self._title = title
        pre = set(preselected or [])
        self._rows = [_Row(label=lbl, value=val, selected=(val in pre)) for lbl, val in items]
        self._allow_freeform = allow_freeform
        self._freeform_placeholder = freeform_placeholder
        self._hint = hint

    def compose(self) -> ComposeResult:
        with Vertical(classes="wizard-panel"):
            yield Label(self._title, classes="wizard-title")
            self._listview = ListView(id="wizard-multi-list")
            yield self._listview
            if self._allow_freeform:
                self._input = Input(
                    placeholder=self._freeform_placeholder, id="wizard-multi-free"
                )
                yield self._input
            yield Label(self._hint, classes="wizard-hint")

    def on_mount(self) -> None:
        self._rerender_rows()
        # If we have nothing to toggle but a free-form input is available,
        # focus the input directly — otherwise the user lands on an empty
        # ListView and has to Tab/click before they can type anything
        # (the Telegram-whitelist wizard step exercises this exact case).
        if self._allow_freeform and not self._rows:
            self._input.focus()
        else:
            self._listview.focus()

    def _rerender_rows(self) -> None:
        self._listview.clear()
        for row in self._rows:
            mark = "[x]" if row.selected else "[ ]"
            self._listview.append(ListItem(Label(f"{mark} {row.label}")))
        if self._rows:
            self._listview.index = 0

    def action_toggle(self) -> None:
        idx = self._listview.index or 0
        if 0 <= idx < len(self._rows):
            self._rows[idx].selected = not self._rows[idx].selected
            self._rerender_rows()
            self._listview.index = idx

    def action_submit(self) -> None:
        chosen = [r.value for r in self._rows if r.selected]
        if self._allow_freeform:
            text = (self.query_one("#wizard-multi-free", Input).value or "").strip()
            extras = [s.strip() for s in text.replace("\n", ",").split(",") if s.strip()]
            chosen.extend(extras)
        self.dismiss(chosen)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        del event
        self.action_submit()

    def on_key(self, event: events.Key) -> None:
        # Ensure space toggling works only when the list (not the free-form
        # input) has focus, so users can type spaces inside their freeform
        # text without flipping rows.
        if event.key == "space" and self._allow_freeform:
            inp = self.query_one("#wizard-multi-free", Input) if self._allow_freeform else None
            if inp is not None and self.focused is inp:
                return  # let the input keep the space
        # Otherwise fall through to the binding system.

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_quit_wizard(self) -> None:
        self.dismiss(["__wizard_cancel__"])  # sentinel
