"""Smoke + functional tests for individual wizard modal screens."""

from __future__ import annotations

from textual.app import App, ComposeResult

from veles.tui.wizard.screens import (
    ChoiceScreen,
    ConfirmScreen,
    InputScreen,
    MultiSelectScreen,
    ProgressScreen,
)
from veles.tui.wizard.screens.choice import ChoiceItem


class _Host(App):
    """Pushes one screen on mount; captures the dismissed value."""

    def __init__(self, screen) -> None:
        super().__init__()
        self._screen = screen
        self.picked = "SENTINEL"

    def on_mount(self) -> None:
        def _capture(value):
            self.picked = value

        self.push_screen(self._screen, _capture)

    def compose(self) -> ComposeResult:
        return iter(())


# ---------------- ChoiceScreen ----------------


async def test_choice_screen_enter_picks_default():
    items = [
        ChoiceItem(label="English", value="en"),
        ChoiceItem(label="Русский", value="ru"),
    ]
    screen = ChoiceScreen("Language", items, default="ru")
    app = _Host(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
    assert app.picked == "ru"


async def test_choice_screen_arrow_then_enter():
    items = [
        ChoiceItem(label="A", value="a"),
        ChoiceItem(label="B", value="b"),
        ChoiceItem(label="C", value="c"),
    ]
    screen = ChoiceScreen("Pick", items, default="a")
    app = _Host(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause()
    assert app.picked == "b"


async def test_choice_screen_highlight_callback_fires_on_navigation():
    """Down/Up movement triggers `on_highlight_changed` with the
    highlighted item's value — used by ThemeStep for live preview."""
    seen: list[str] = []
    items = [
        ChoiceItem(label="A", value="a"),
        ChoiceItem(label="B", value="b"),
        ChoiceItem(label="C", value="c"),
    ]
    screen = ChoiceScreen(
        "Pick",
        items,
        default="a",
        on_highlight_changed=seen.append,
    )
    app = _Host(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Initial mount fires Highlighted once with the default.
        await pilot.press("down")  # → b
        await pilot.press("down")  # → c
        await pilot.press("escape")
        await pilot.pause()
    # Sequence must include b and c after the initial highlight.
    assert "b" in seen and "c" in seen


async def test_choice_screen_escape_dismisses_none():
    items = [ChoiceItem(label="X", value="x")]
    screen = ChoiceScreen("Pick", items)
    app = _Host(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    assert app.picked is None


# ---------------- ConfirmScreen ----------------


async def test_confirm_y_returns_true():
    screen = ConfirmScreen("Q", "Proceed?")
    app = _Host(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
    assert app.picked is True


async def test_confirm_n_returns_false():
    screen = ConfirmScreen("Q", "Proceed?")
    app = _Host(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
    assert app.picked is False


async def test_confirm_arrow_right_then_enter_picks_no():
    screen = ConfirmScreen("Q", "Proceed?", default=True)
    app = _Host(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Default focus is Yes. → moves to No. Enter confirms focused.
        await pilot.press("right")
        await pilot.press("enter")
        await pilot.pause()
    assert app.picked is False


async def test_confirm_arrow_left_returns_to_yes():
    screen = ConfirmScreen("Q", "Proceed?", default=False)
    app = _Host(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Default focus is No when default=False. ← moves to Yes.
        await pilot.press("left")
        await pilot.press("enter")
        await pilot.pause()
    assert app.picked is True


async def test_confirm_enter_uses_default_focus():
    screen = ConfirmScreen("Q", "Proceed?", default=True)
    app = _Host(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        # No arrows pressed — Enter on the focused default (Yes).
        await pilot.press("enter")
        await pilot.pause()
    assert app.picked is True


async def test_confirm_escape_returns_none():
    screen = ConfirmScreen("Q", "Proceed?")
    app = _Host(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    assert app.picked is None


# ---------------- InputScreen ----------------


async def test_input_screen_captures_text():
    screen = InputScreen("Q", prompt="API key")
    app = _Host(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("a", "b", "c")
        await pilot.press("enter")
        await pilot.pause()
    assert app.picked == "abc"


async def test_input_screen_default_value():
    screen = InputScreen("Q", default="seed")
    app = _Host(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
    assert app.picked == "seed"


async def test_input_screen_escape_returns_none():
    screen = InputScreen("Q")
    app = _Host(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    assert app.picked is None


# ---------------- MultiSelectScreen ----------------


async def test_multiselect_with_preselected_round_trip():
    items = [("Alpha", "a"), ("Beta", "b"), ("Gamma", "g")]
    screen = MultiSelectScreen("Pick", items, preselected=["a"])
    app = _Host(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()
    assert app.picked == ["a"]


async def test_multiselect_freeform_added_to_result():
    items = [("Alpha", "a")]
    screen = MultiSelectScreen("Pick", items, allow_freeform=True)
    app = _Host(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Don't toggle a; jump straight to free-form via Tab.
        await pilot.press("tab")
        await pilot.press("@", "f", "o", "o")
        await pilot.press("ctrl+s")
        await pilot.pause()
    assert app.picked == ["@foo"]


async def test_multiselect_freeform_focused_when_list_empty():
    """M106: When MultiSelectScreen has no preset items but free-form is
    allowed (Telegram whitelist wizard step), the Input must receive
    focus immediately so the user can type without an extra Tab/click."""
    screen = MultiSelectScreen("Allowlist", [], allow_freeform=True)
    app = _Host(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Type without Tabbing — the focused Input should accept it.
        await pilot.press("@", "u", "s", "e", "r")
        await pilot.press("ctrl+s")
        await pilot.pause()
    assert app.picked == ["@user"]


async def test_multiselect_listview_focused_when_items_present():
    """Sanity guard: when items are present, focus stays on the ListView
    (toggling with Space is the primary path)."""
    items = [("Alpha", "a")]
    screen = MultiSelectScreen("Pick", items, allow_freeform=True)
    app = _Host(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert screen._listview.has_focus
        assert not screen._input.has_focus


# ---------------- ProgressScreen ----------------


async def test_progress_screen_closes_on_enter():
    screen = ProgressScreen("Done", ["line A", "line B"])
    app = _Host(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
    assert app.picked is None


# ---------------- ChoiceScreen filterable ----------------


async def test_choice_screen_filter_narrows_visible_items():
    items = [
        ChoiceItem(label="anthropic/claude-sonnet-4.6", value="anthropic/claude-sonnet-4.6"),
        ChoiceItem(label="anthropic/claude-haiku-4.5", value="anthropic/claude-haiku-4.5"),
        ChoiceItem(label="openai/gpt-4o", value="openai/gpt-4o"),
        ChoiceItem(label="google/gemini-2.5-pro", value="google/gemini-2.5-pro"),
    ]
    screen = ChoiceScreen("Pick", items, default=items[0].value, filterable=True)
    app = _Host(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Type "haiku" into the focused filter Input.
        await pilot.press("h", "a", "i", "k", "u")
        await pilot.pause()
        assert [it.value for it in screen._visible_items] == [
            "anthropic/claude-haiku-4.5"
        ]
        # Arrow-down moves focus from Input → ListView, then Enter picks.
        await pilot.press("down")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
    assert app.picked == "anthropic/claude-haiku-4.5"


async def test_choice_screen_filter_no_match_keeps_listview_empty_but_safe():
    items = [
        ChoiceItem(label="alpha", value="a"),
        ChoiceItem(label="beta", value="b"),
    ]
    screen = ChoiceScreen("Pick", items, default="a", filterable=True)
    app = _Host(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("z", "z", "z")
        await pilot.pause()
        assert screen._visible_items == []
        # Enter on empty list must not crash and must not dismiss.
        await pilot.press("enter")
        await pilot.pause()
        assert app.picked == "SENTINEL"
        # Clear filter — full list comes back.
        await pilot.press("backspace", "backspace", "backspace")
        await pilot.pause()
        assert len(screen._visible_items) == 2


async def test_choice_screen_non_filterable_has_no_input():
    items = [ChoiceItem(label="A", value="a"), ChoiceItem(label="B", value="b")]
    screen = ChoiceScreen("Pick", items, default="a")
    app = _Host(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert screen._filter_input is None
