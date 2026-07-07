"""Minimal Textual App that hosts a wizard run.

Lives outside the main `TuiApp` for cleanliness: the chat surface
isn't mounted until the wizard finishes, and the wizard's modal-only
flow doesn't need ChatLog/StatusBar/Composer. Exits with the accumulated
answers (or None on cancel) so the caller can persist them and proceed
to launch the main TUI.
"""

from __future__ import annotations

from typing import Any, ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Label

from veles.tui.wizard.runner import WizardCancelled, WizardRunner
from veles.tui.wizard.step import WizardStep


class WizardApp(App[dict[str, Any] | None]):
    """Runs `steps` sequentially via push_screen modal flow.

    `run()` returns the answers dict on success, None on cancel.
    """

    CSS = """
    Screen { align: center middle; background: $surface; }
    .wizard-shell {
        background: $surface;
        padding: 1 2;
        height: auto;
        width: auto;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("ctrl+q", "cancel_wizard", "quit", priority=True),
    ]

    def __init__(
        self,
        steps: list[WizardStep],
        *,
        title: str = "Veles setup",
        initial: dict[str, Any] | None = None,
    ) -> None:
        super().__init__()
        self._steps = steps
        self._title = title
        self._initial = dict(initial or {})
        self.result: dict[str, Any] | None = None

    def compose(self) -> ComposeResult:
        with Vertical(classes="wizard-shell"):
            yield Label(self._title)

    def on_mount(self) -> None:
        # Apply the user's preferred theme up front so the wizard looks
        # and feels native. First-run users have no saved config, so we
        # fall back to the project default (everforest). Live theme
        # changes inside the wizard are handled by ThemeStep.
        from veles.core.user_config import load_user_config
        from veles.tui.theme_bridge import apply_to_app

        cfg = load_user_config()
        apply_to_app(self, (cfg.tui_theme if cfg else None) or "everforest")
        self.run_worker(self._drive_wizard(), exclusive=True, group="wizard")

    async def _drive_wizard(self) -> None:
        runner = WizardRunner(self, self._steps)
        try:
            answers = await runner.run(initial=self._initial)
        except WizardCancelled:
            self.result = None
            self.exit(None)
            return
        self.result = answers
        self.exit(answers)

    def action_cancel_wizard(self) -> None:
        self.result = None
        self.exit(None)
