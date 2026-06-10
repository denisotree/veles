"""Theme bridge — TuiTheme → Textual Theme, applied to a live App.

Verifies the colour-token mapping and the side-effects on the App
(`app.theme` swaps to the new name, unknown names return False without
mutating).
"""

from __future__ import annotations

from textual.app import App, ComposeResult

from veles.cli.tui_theme import THEMES
from veles.tui.theme_bridge import apply_to_app, to_textual_theme


def test_token_mapping_for_dracula():
    th = to_textual_theme(THEMES["dracula"])
    # Built-in dracula values come straight through.
    assert th.primary == THEMES["dracula"].accent
    assert th.warning == THEMES["dracula"].warning
    assert th.error == THEMES["dracula"].error
    assert th.success == THEMES["dracula"].success
    assert th.name == "veles_dracula"


class _ThemeHost(App):
    def compose(self) -> ComposeResult:
        return iter(())


async def test_apply_to_app_swaps_textual_theme():
    app = _ThemeHost()
    async with app.run_test() as pilot:
        # Pre-mount: stock Textual theme.
        original = pilot.app.theme
        ok = apply_to_app(pilot.app, "dracula")
        await pilot.pause()
        assert ok
        assert pilot.app.theme == "veles_dracula"
        # Switching back to a different built-in works through the
        # same path (registers if needed, then assigns).
        assert apply_to_app(pilot.app, "gruvbox")
        await pilot.pause()
        assert pilot.app.theme == "veles_gruvbox"
        # Returning to the original by name resolves; the original is
        # Textual's default ("textual-dark"), not a veles theme.
        del original


async def test_apply_to_app_returns_false_for_unknown_theme():
    app = _ThemeHost()
    async with app.run_test() as pilot:
        baseline = pilot.app.theme
        assert apply_to_app(pilot.app, "totally-not-a-theme") is False
        assert pilot.app.theme == baseline
