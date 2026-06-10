"""Inline approval / trust prompt anchored above the Composer.

When the agent's permission gate trips (sensitive-tool trust ladder or
risk-class approval), the TUI replaces the centred `ApprovalScreen` /
`TrustScreen` modals with this widget mounted right above the Composer.
The user sees:

- a one-line title (what is being asked),
- an optional body (tool name, reason, arguments),
- a `ListView` of options.

Navigation: ↑/↓ moves selection. `Enter` confirms the current row. Each
option can declare a `hotkey` (`"1"`, `"y"`, …) that selects the option
directly. `Esc` returns `default_key` — typically the safest answer
(`TrustChoice.REFUSE` or `False`).

Result delivery is via an `asyncio.Future` so the host coroutine can
`await` it.  `TuiApp.composer_prompt` is the orchestrator that mounts
the widget, hides the Composer, and waits for the future.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, ClassVar

from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Input, Label, ListItem, ListView, Static


@dataclass(frozen=True, slots=True)
class PromptOption:
    key: Any
    label: str
    hotkey: str | None = None
    # M115.4: when True, selecting this option opens an inline Input for
    # the user to type a freeform answer. The future resolves with a
    # `FreeformAnswer(text=…)` so callers can distinguish "picked option"
    # from "typed custom text". Used for clarification questions from
    # the agent manager (VISION §5.3, §7.2 universal-prompt pattern).
    freeform: bool = False


@dataclass(frozen=True, slots=True)
class FreeformAnswer:
    """Marker wrapping the user's typed answer to a freeform option.
    Lets callers tell "selected option with key X" apart from "typed Y"
    without inspecting the option list."""

    text: str


class ComposerPrompt(Vertical):
    DEFAULT_CSS = """
    ComposerPrompt {
        background: $surface;
        border-top: thick $warning;
        padding: 0 1;
        height: auto;
        max-height: 14;
    }
    ComposerPrompt Label.veles-prompt-title {
        color: $warning;
        text-style: bold;
    }
    ComposerPrompt Static.veles-prompt-body {
        color: $text;
        height: auto;
        margin-bottom: 1;
    }
    ComposerPrompt ListView {
        height: auto;
        max-height: 6;
    }
    ComposerPrompt Label.veles-prompt-hint {
        color: $text-muted;
        text-style: italic;
    }
    """

    can_focus: ClassVar[bool] = True

    def __init__(
        self,
        *,
        question: str,
        body: str | None,
        options: list[PromptOption],
        default_key: Any,
        future: asyncio.Future[Any],
    ) -> None:
        super().__init__(id="veles-composer-prompt")
        if not options:
            raise ValueError("ComposerPrompt requires at least one option")
        self._question = question
        self._body = body
        self._options = options
        self._default_key = default_key
        self._future = future
        self._list: ListView | None = None
        # M115.4: when set, the user picked a freeform option and is
        # typing the answer into `_input`. `on_key` then routes Enter to
        # `_resolve_freeform` and Escape to the default.
        self._freeform_input: Input | None = None
        self._freeform_active: bool = False

    def compose(self) -> ComposeResult:
        yield Label(self._question, classes="veles-prompt-title")
        if self._body:
            yield Static(self._body, classes="veles-prompt-body")
        items: list[ListItem] = []
        for opt in self._options:
            tag = f"[{opt.hotkey}] " if opt.hotkey else ""
            items.append(ListItem(Label(f"{tag}{opt.label}")))
        self._list = ListView(*items)
        yield self._list
        yield Label(
            "↑/↓ navigate · Enter confirm · Esc cancel",
            classes="veles-prompt-hint",
        )

    def on_mount(self) -> None:
        # Preselect the default option so Enter on a fresh prompt returns
        # the safest answer, matching the legacy modal's behaviour.
        default_idx = 0
        for i, opt in enumerate(self._options):
            if opt.key == self._default_key:
                default_idx = i
                break
        if self._list is not None:
            self._list.index = default_idx
            self._list.focus()

    def on_key(self, event: events.Key) -> None:
        if self._future.done():
            return
        # M115.4: while the freeform input is active, Enter resolves
        # with the typed text; Escape returns the default key. Hotkeys
        # and arrow navigation are off so they don't fight the user's
        # typing inside the input.
        if self._freeform_active:
            if event.key == "enter":
                event.stop()
                text = self._freeform_input.value if self._freeform_input else ""
                self._resolve(FreeformAnswer(text=text))
                return
            if event.key == "escape":
                event.stop()
                self._resolve(self._default_key)
                return
            return
        if event.key == "enter":
            event.stop()
            idx = self._selected_index()
            self._activate_option(self._options[idx])
            return
        if event.key == "escape":
            event.stop()
            self._resolve(self._default_key)
            return
        for opt in self._options:
            if opt.hotkey and event.key == opt.hotkey:
                event.stop()
                self._activate_option(opt)
                return

    def _activate_option(self, opt: PromptOption) -> None:
        """Either resolve directly (normal option) or open the freeform
        input (option declared `freeform=True`)."""
        if opt.freeform:
            self._enter_freeform_mode()
            return
        self._resolve(opt.key)

    def _enter_freeform_mode(self) -> None:
        if self._freeform_active or self._future.done():
            return
        self._freeform_active = True
        self._freeform_input = Input(
            placeholder="type your answer, Enter to submit, Esc to cancel",
            id="veles-prompt-freeform",
        )
        self.mount(self._freeform_input)
        self._freeform_input.focus()

    def _selected_index(self) -> int:
        if self._list is None:
            return 0
        idx = self._list.index
        if idx is None or idx < 0 or idx >= len(self._options):
            return 0
        return idx

    def _resolve(self, key: Any) -> None:
        if not self._future.done():
            self._future.set_result(key)


__all__ = ["ComposerPrompt", "PromptOption", "FreeformAnswer"]
