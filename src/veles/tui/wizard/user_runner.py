"""Sync entry point for the first-run TUI wizard.

Called from `cli/__init__.py` (or `tui/__init__.py`) before launching
the main TuiApp when:
  - `~/.veles/config.toml` is missing,
  - stdin is a TTY,
  - the command isn't a bootstrap verb.

Returns the saved `UserConfig` on success or None on cancel.
"""

from __future__ import annotations

from veles.core.user_config import UserConfig, save_user_config
from veles.tui.wizard.app import WizardApp
from veles.tui.wizard.user_steps import user_wizard_steps


def run_user_wizard_tui() -> tuple[UserConfig | None, dict]:
    """Returns (saved config | None, raw answers dict).

    The raw answers carry extras like `init_project_here` that the caller
    chains into the project wizard."""
    app = WizardApp(steps=user_wizard_steps())
    answers = app.run() or {}
    if not answers:
        return None, {}
    cfg = UserConfig(
        language=answers.get("language", "en"),
        default_provider=answers.get("default_provider", "openrouter"),
        tui_theme=answers.get("tui_theme", "everforest"),
        default_model=answers.get("default_model"),
    )
    try:
        save_user_config(cfg)
    except OSError:
        pass
    return cfg, answers


__all__ = ["run_user_wizard_tui"]
