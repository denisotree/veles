"""Modal overlays that gate sensitive tool dispatch.

Two screens, one base shape:

  `ApprovalScreen` — `(tool_name, args, reason)` → `bool` (allow/deny).
      Default = deny. `Y` approves, anything else (Escape, N, Enter)
      denies. Used by `Permission Engine` approval-required outcomes.

  `TrustScreen` — `(tool_name)` → `TrustChoice`. Four-option ladder:
      `1` = ONCE, `2` = ALWAYS_PROJECT, `3` = ALWAYS_GLOBAL,
      `4` / Escape / Enter = REFUSE. Mirrors the legacy stdin prompt
      from `core/trust.py:_default_prompter`.

Both are pushed from `AgentBridge` via `call_from_thread + push_screen_wait`
so the worker thread blocks until the user makes a choice.
"""

from __future__ import annotations

from typing import Any, ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, Static

from veles.core.trust import TrustChoice

_CARD_CSS = """
    ModalScreen {
        align: center middle;
    }
    ModalScreen > Vertical {
        background: $surface;
        border: thick $warning;
        padding: 1 2;
        width: 80;
        height: auto;
        max-height: 24;
    }
    ModalScreen Label.veles-modal-title {
        color: $warning;
        text-style: bold;
        margin-bottom: 1;
    }
    ModalScreen Static.veles-modal-body {
        height: auto;
        color: $text;
        margin-bottom: 1;
    }
    ModalScreen Label.veles-modal-hint {
        color: $text-muted;
        text-style: italic;
    }
"""


class ApprovalScreen(ModalScreen[bool]):
    """Yes/no gate. Default = deny so an accidental Enter never approves
    a sensitive op (matches the legacy `[y/N]` convention)."""

    DEFAULT_CSS = _CARD_CSS

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("y", "approve", "approve", priority=True),
        Binding("Y", "approve", "approve", priority=True, show=False),
        Binding("n", "deny", "deny", priority=True),
        Binding("N", "deny", "deny", priority=True, show=False),
        Binding("escape", "deny", "deny", priority=True),
        Binding("enter", "deny", "deny", priority=True),
    ]

    def __init__(self, tool_name: str, arguments: dict[str, Any], reason: str) -> None:
        super().__init__()
        self._tool_name = tool_name
        self._arguments = arguments
        self._reason = reason

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Approval required", classes="veles-modal-title")
            body_text = (
                f"Tool: {self._tool_name}\n"
                f"Reason: {self._reason or '(unspecified)'}\n"
                f"Arguments: {self._arguments}"
            )
            yield Static(body_text, classes="veles-modal-body")
            yield Label("[y] approve   [n / Esc / Enter] deny", classes="veles-modal-hint")

    def action_approve(self) -> None:
        self.dismiss(True)

    def action_deny(self) -> None:
        self.dismiss(False)


class TrustScreen(ModalScreen[TrustChoice]):
    """Four-way trust ladder. Default = REFUSE for the same safety
    reason as `ApprovalScreen`."""

    DEFAULT_CSS = _CARD_CSS

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("1", "choose_once", "once", priority=True),
        Binding("2", "choose_project", "always project", priority=True),
        Binding("3", "choose_global", "always global", priority=True),
        Binding("4", "refuse", "refuse", priority=True),
        Binding("escape", "refuse", "refuse", priority=True),
        Binding("enter", "refuse", "refuse", priority=True),
    ]

    def __init__(self, tool_name: str) -> None:
        super().__init__()
        self._tool_name = tool_name

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(
                f"Tool {self._tool_name!r} wants to execute",
                classes="veles-modal-title",
            )
            yield Static(
                "  [1] Once (this call only)\n"
                "  [2] Always for this project\n"
                "  [3] Always everywhere\n"
                "  [4] Refuse",
                classes="veles-modal-body",
            )
            yield Label(
                "Press 1-4, or Esc / Enter to refuse.",
                classes="veles-modal-hint",
            )

    def action_choose_once(self) -> None:
        self.dismiss(TrustChoice.ONCE)

    def action_choose_project(self) -> None:
        self.dismiss(TrustChoice.ALWAYS_PROJECT)

    def action_choose_global(self) -> None:
        self.dismiss(TrustChoice.ALWAYS_GLOBAL)

    def action_refuse(self) -> None:
        self.dismiss(TrustChoice.REFUSE)
