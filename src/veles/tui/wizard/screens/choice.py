"""Pick one item from a fixed list (radio-style)."""

from __future__ import annotations

import contextlib
from collections.abc import Callable
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
class ChoiceItem:
    label: str
    value: str
    description: str = ""


class ChoiceScreen(ModalScreen[str | None]):
    """Returns the picked `value`, or None on Esc (BACK signal at the
    runner level)."""

    DEFAULT_CSS = (
        WIZARD_CSS
        + """
    ChoiceScreen {
        align: center middle;
    }
    ChoiceScreen ListView {
        height: auto;
        max-height: 18;
    }
    ChoiceScreen ListItem {
        padding: 0 1;
    }
    ChoiceScreen ListItem.--highlight {
        background: $primary 30%;
    }
    ChoiceScreen Input.wizard-filter {
        margin-bottom: 1;
    }
    """
    )

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "back", priority=True),
        Binding("ctrl+q", "quit_wizard", "quit", priority=True),
    ]

    def __init__(
        self,
        title: str,
        items: list[ChoiceItem],
        *,
        subtitle: str = "",
        default: str | None = None,
        hint: str = "↑/↓ navigate · Enter confirm · Esc back · Ctrl+Q quit",
        on_highlight_changed: Callable[[str], None] | None = None,
        filterable: bool = False,
        filter_placeholder: str = "type to filter…",
    ) -> None:
        super().__init__()
        self._title = title
        self._subtitle = subtitle
        self._items = items
        self._default = default
        self._hint = hint
        # Optional callback fired with the item's `value` every time the
        # ListView cursor moves. Used by ThemeStep for live preview.
        self._on_highlight_changed = on_highlight_changed
        self._filterable = filterable
        self._filter_placeholder = filter_placeholder
        # Items currently shown in ListView — same as `_items` until the
        # user types into the filter input. Tracked separately so Enter
        # picks from the filtered view, not the full list.
        self._visible_items: list[ChoiceItem] = list(items)
        self._filter_input: Input | None = None

    def compose(self) -> ComposeResult:
        with Vertical(classes="wizard-panel"):
            yield Label(self._title, classes="wizard-title")
            if self._subtitle:
                yield Label(self._subtitle, classes="wizard-subtitle")
            if self._filterable:
                self._filter_input = Input(
                    placeholder=self._filter_placeholder,
                    classes="wizard-filter",
                    id="wizard-choice-filter",
                )
                yield self._filter_input
            self._listview = ListView(id="wizard-choice-list")
            yield self._listview
            hint = self._hint
            if self._filterable:
                hint = "Type to filter · " + hint
            yield Label(hint, classes="wizard-hint")

    def on_mount(self) -> None:
        self._populate(initial=True)
        # Filter input gets focus first when present so the user can start
        # typing immediately; ↑/↓ still navigate the ListView because the
        # Input only consumes printable keys (Textual default).
        if self._filterable and self._filter_input is not None:
            self._filter_input.focus()
        else:
            self._listview.focus()

    def _populate(self, *, initial: bool = False) -> None:
        """(Re)build ListView from `_visible_items`. Restores cursor to the
        previously-selected value when possible so typing into the filter
        doesn't visually jump the cursor around unnecessarily."""
        prev_value: str | None = None
        if not initial:
            idx = self._listview.index or 0
            if 0 <= idx < len(self._visible_items):
                prev_value = self._visible_items[idx].value
        self._listview.clear()
        default_idx = 0
        for i, item in enumerate(self._visible_items):
            label = f"{item.label}"
            if item.description:
                label = f"{item.label}  —  {item.description}"
            self._listview.append(ListItem(Label(label)))
            matches_default = initial and self._default is not None and item.value == self._default
            matches_prev = not initial and prev_value is not None and item.value == prev_value
            if matches_default or matches_prev:
                default_idx = i
        if self._visible_items:
            self._listview.index = default_idx

    def on_input_changed(self, event: Input.Changed) -> None:
        if not self._filterable or event.input is not self._filter_input:
            return
        query = (event.value or "").strip().lower()
        if not query:
            self._visible_items = list(self._items)
        else:
            self._visible_items = [
                it for it in self._items if query in it.label.lower() or query in it.value.lower()
            ]
        self._populate()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        del event
        index = self._listview.index or 0
        if 0 <= index < len(self._visible_items):
            self.dismiss(self._visible_items[index].value)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Fire the optional on_highlight_changed callback on cursor moves."""
        del event
        if self._on_highlight_changed is None:
            return
        index = self._listview.index or 0
        if 0 <= index < len(self._visible_items):
            with contextlib.suppress(Exception):
                self._on_highlight_changed(self._visible_items[index].value)

    def on_key(self, event: events.Key) -> None:
        if event.key == "enter":
            index = self._listview.index or 0
            if 0 <= index < len(self._visible_items):
                event.stop()
                self.dismiss(self._visible_items[index].value)
        elif (
            event.key in ("down", "up")
            and self._filterable
            and self._filter_input is not None
            and self._filter_input.has_focus
        ):
            # Hand keyboard focus to the ListView so arrows navigate items
            # without the user having to Tab. Forward the original key so
            # the cursor moves immediately, not on the next press.
            event.stop()
            self._listview.focus()
            if event.key == "down" and self._visible_items:
                self._listview.index = min(
                    (self._listview.index or 0) + 1, len(self._visible_items) - 1
                )
            elif event.key == "up" and self._visible_items:
                self._listview.index = max((self._listview.index or 0) - 1, 0)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_quit_wizard(self) -> None:
        self.dismiss("__wizard_cancel__")
