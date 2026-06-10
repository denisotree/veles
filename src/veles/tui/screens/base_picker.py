"""Generic fuzzy-filter picker modal.

A `PickerScreen[T]` accepts a list of items (each carrying a display
label, a searchable haystack, and a typed value) and dismisses itself
with the chosen value — or `None` if the user pressed Escape.

The filter is intentionally simple: case-insensitive substring match
against the haystack string. Phase-5 doesn't try to ship full fuzzy
ranking — it's enough for picking from <100 items, which covers
sessions, models, and themes for the foreseeable future.

Subclasses tend to fit on one screen: they implement `build_items()`
and feed the resulting list into `super().__init__`. The base screen
owns layout, filtering, keybindings, and dismissal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Generic, TypeVar

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, ListItem, ListView, Static

T = TypeVar("T")


# PEP-695 type-parameter syntax (`class PickerItem[T]:`) doesn't compose
# cleanly with `@dataclass(slots=True)` in 3.13, and the screen-side
# `ModalScreen[T | None]` base needs a runtime TypeVar to forward `T`.
# Keep the classic `Generic[T]` style here; UP046 noqa-flagged.
@dataclass(slots=True)
class PickerItem(Generic[T]):  # noqa: UP046
    """One row in a picker. `value` is what `dismiss()` returns; `label`
    is what the user sees; `haystack` is what the filter matches
    against (usually `label` plus extra metadata)."""

    label: str
    haystack: str
    value: T


class PickerScreen(ModalScreen[T | None], Generic[T]):  # noqa: UP046
    DEFAULT_CSS = """
    PickerScreen {
        align: center middle;
    }
    PickerScreen > Vertical {
        background: $surface;
        border: tall $primary;
        padding: 1 2;
        width: 80%;
        max-width: 100;
        height: 70%;
        max-height: 30;
    }
    PickerScreen Label.veles-picker-title {
        color: $accent;
        margin-bottom: 1;
    }
    PickerScreen Input {
        margin-bottom: 1;
    }
    PickerScreen ListView {
        height: 1fr;
    }
    PickerScreen Static.veles-picker-empty {
        color: $text-muted;
        padding: 1;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "cancel", priority=True),
    ]

    def __init__(
        self,
        title: str,
        items: list[PickerItem[T]],
        *,
        empty_message: str = "(no matches)",
        placeholder: str = "type to filter…",
    ) -> None:
        super().__init__()
        self._title = title
        self._items = items
        self._empty_message = empty_message
        self._placeholder = placeholder
        # `_filter` and `_visible` track the current filter input and
        # the items currently mounted. Both are reset on every keystroke
        # via `on_input_changed`.
        self._filter: str = ""
        self._visible: list[PickerItem[T]] = list(items)
        # Tests inspect this to confirm what's on screen without
        # walking the widget tree.
        self.visible_labels: list[str] = [it.label for it in items]

    # ---- composition ----

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self._title, classes="veles-picker-title")
            yield Input(placeholder=self._placeholder, id="veles-picker-filter")
            self._listview = ListView(id="veles-picker-list")
            yield self._listview
            self._empty = Static(self._empty_message, classes="veles-picker-empty")
            self._empty.display = False
            yield self._empty

    def on_mount(self) -> None:
        self._populate(self._items)
        # ListView keeps focus so Up/Down work without Tab. Printable keys
        # are forwarded to the filter input via on_key (M81).
        self._listview.focus()

    # ---- keyboard ----

    def on_key(self, event: events.Key) -> None:
        """Forward typing to the hidden filter input while keeping ListView
        focused, so arrow navigation works without an explicit Tab. Enter
        and Escape stay on their default ListView/binding paths."""
        inp = self.query_one("#veles-picker-filter", Input)
        if self.focused is inp:
            return
        if event.key == "backspace":
            if inp.value:
                inp.value = inp.value[:-1]
                event.stop()
            return
        ch = event.character
        if ch and event.is_printable and len(ch) == 1:
            inp.value = inp.value + ch
            event.stop()

    # ---- filtering ----

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "veles-picker-filter":
            return
        self._filter = event.value.strip().lower()
        if not self._filter:
            filtered = list(self._items)
        else:
            filtered = [it for it in self._items if self._filter in it.haystack.lower()]
        self._populate(filtered)

    def _populate(self, items: list[PickerItem[T]]) -> None:
        self._visible = items
        self.visible_labels = [it.label for it in items]
        # `ListView.clear` + `append` is the supported full-refresh
        # path in Textual 8.x; rebuilding is fine here because filters
        # change wholesale rather than per-row.
        self._listview.clear()
        for it in items:
            self._listview.append(ListItem(Label(it.label)))
        # Position the cursor on the first row so Enter selects it without
        # an extra Down keypress (M81 — ListView starts unselected otherwise).
        if items:
            self._listview.index = 0
        self._empty.display = not items

    # ---- selection ----

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter inside the filter input: pick the highlighted row.
        Without a selection (empty list), the screen stays open."""
        del event
        if not self._visible:
            return
        index = self._listview.index or 0
        index = min(index, len(self._visible) - 1)
        self.dismiss(self._visible[index].value)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """User clicked or pressed Enter on a row directly."""
        del event
        index = self._listview.index or 0
        if 0 <= index < len(self._visible):
            self.dismiss(self._visible[index].value)

    def action_cancel(self) -> None:
        self.dismiss(None)
