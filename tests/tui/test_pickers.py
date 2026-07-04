"""Picker modals — filter, dismiss with selection, dismiss on Escape.

The base picker is exercised through a minimal host App. The
session / model / theme pickers are checked end-to-end inside the
full `TuiApp` to assert the post-pick state mutation.
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Input

from veles.core.provider import Message
from veles.core.session_state import AppState
from veles.tui.app import TuiApp
from veles.tui.screens import (
    ModelPickerScreen,
    PickerItem,
    PickerScreen,
    SessionPickerScreen,
    ThemePickerScreen,
)

# ---------------- base picker ----------------


class _PickerHost(App):
    """Pushes a picker on mount; captures the dismissed value."""

    def __init__(self, screen: PickerScreen) -> None:
        super().__init__()
        self._screen = screen
        self.picked: object | None = "SENTINEL"

    def on_mount(self) -> None:
        def _on_dismiss(value):
            self.picked = value

        self.push_screen(self._screen, _on_dismiss)

    def compose(self) -> ComposeResult:
        return iter(())


async def test_picker_filter_shrinks_visible_set():
    items = [
        PickerItem(label="alpha", haystack="alpha", value="a"),
        PickerItem(label="beta", haystack="beta", value="b"),
        PickerItem(label="gamma", haystack="gamma", value="g"),
    ]
    screen = PickerScreen("Pick", items)
    app = _PickerHost(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert screen.visible_labels == ["alpha", "beta", "gamma"]
        screen.query_one(Input).value = "g"
        await pilot.pause()
        assert screen.visible_labels == ["gamma"]


async def test_picker_enter_in_filter_dismisses_with_first_match():
    items = [
        PickerItem(label="alpha", haystack="alpha", value="a"),
        PickerItem(label="beta", haystack="beta", value="b"),
    ]
    app = _PickerHost(PickerScreen("Pick", items))
    async with app.run_test() as pilot:
        await pilot.pause()
        # Filter input has focus; pressing enter picks the first row.
        await pilot.press("enter")
        await pilot.pause()
    assert app.picked == "a"


async def test_picker_escape_dismisses_with_none():
    items = [PickerItem(label="alpha", haystack="alpha", value="a")]
    app = _PickerHost(PickerScreen("Pick", items))
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    assert app.picked is None


async def test_picker_empty_list_shows_message():
    screen = PickerScreen("Pick", [], empty_message="nothing here")
    app = _PickerHost(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Enter on an empty list keeps the screen open and returns no value.
        await pilot.press("enter")
        await pilot.pause()
    assert app.picked == "SENTINEL"  # `_on_dismiss` never fired


# ---------------- domain pickers ----------------


async def test_session_picker_lists_recent_sessions(tmp_project):
    project, store = tmp_project
    s1 = store.create_session()
    store.append_turn(s1, Message(role="user", content="ping"))
    s2 = store.create_session()
    store.append_turn(s2, Message(role="user", content="pong"))

    screen = SessionPickerScreen(store, current=s1)
    app = _PickerHost(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        joined = " ".join(screen.visible_labels)
        assert s1 in joined and s2 in joined
        # Current marker shows up on the active session.
        assert "* " + s1 in joined
    del project


async def test_model_picker_lists_known_models():
    screen = ModelPickerScreen("openrouter")
    app = _PickerHost(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        joined = " ".join(screen.visible_labels)
        assert "anthropic/claude-sonnet-4.6" in joined
        assert "openai/gpt-4o" in joined


async def test_theme_picker_lists_builtins():
    screen = ThemePickerScreen(current="everforest")
    app = _PickerHost(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        joined = " ".join(screen.visible_labels)
        for name in ("everforest", "dracula", "gruvbox", "tokyo-night", "catppuccin"):
            assert name in joined


# ---------------- TuiApp integration ----------------


def _new_app(tmp_project, agent_factory_for, text_response, *, reply: str = "ok"):
    project, store = tmp_project
    return TuiApp(
        state=AppState(session_id=None, provider_name="openrouter", model="m"),
        agent_factory=agent_factory_for(text_response(reply)),
        project=project,
        store=store,
    )


async def test_ctrl_r_opens_session_picker_and_switches(
    tmp_project, agent_factory_for, text_response
):
    _, store = tmp_project
    sid = store.create_session()
    store.append_turn(sid, Message(role="user", content="hello"))

    app = _new_app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+r")
        await pilot.pause()
        # The session-picker is now on the stack. Press enter to take
        # the first (and only) entry.
        await pilot.press("enter")
        await pilot.pause()
    assert app.state.session_id == sid


async def test_slash_model_no_arg_opens_picker(tmp_project, agent_factory_for, text_response):
    app = _new_app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        from veles.tui.widgets.composer import Composer

        composer = pilot.app.query_one(Composer)
        composer.focus()
        composer.text = "/model"
        await pilot.press("enter")
        await pilot.pause()
        # Picker is mounted on top of the chat screen — assertable by
        # screen-stack depth or by querying the ModelPickerScreen.
        assert any(isinstance(s, ModelPickerScreen) for s in pilot.app.screen_stack)
        await pilot.press("enter")  # take first row
        await pilot.pause()
    # First model in the openrouter list.
    from veles.tui.screens.model_picker import known_models

    assert app.state.model == known_models("openrouter")[0]


async def test_slash_model_refresh_opens_picker_with_refresh_flag(
    tmp_project, agent_factory_for, text_response, monkeypatch
):
    """End-to-end: `/model refresh` typed in the composer → slash handler
    → `_open_picker("models:refresh")` → `action_pick_model(refresh=True)`.
    The conftest already stubs `fetch_models`, so no network is touched; we
    spy on the stub instead to assert `refresh=True` reached it."""
    from veles.tui.screens import _model_fetcher

    seen: dict[str, bool] = {}

    def spy(provider: str, *, refresh: bool = False) -> _model_fetcher.ModelList:
        seen["provider"] = provider  # type: ignore[assignment]
        seen["refresh"] = refresh
        return _model_fetcher.ModelList(
            models=_model_fetcher.known_models(provider), source="curated"
        )

    monkeypatch.setattr(_model_fetcher, "fetch_models", spy)

    app = _new_app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        from veles.tui.widgets.composer import Composer

        composer = pilot.app.query_one(Composer)
        composer.focus()
        composer.text = "/model refresh"
        await pilot.press("enter")
        await pilot.pause()
        assert any(isinstance(s, ModelPickerScreen) for s in pilot.app.screen_stack)
    assert seen["provider"] == "openrouter"
    assert seen["refresh"] is True


async def test_ctrl_t_opens_theme_picker_and_sets_state(
    tmp_project, agent_factory_for, text_response
):
    app = _new_app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+t")
        await pilot.pause()
        # Filter to one specific theme.
        from textual.widgets import Input as _Input

        pilot.app.screen.query_one(_Input).value = "dracula"
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
    assert app.state.theme_name == "dracula"


async def test_picker_escape_keeps_state_unchanged(tmp_project, agent_factory_for, text_response):
    app = _new_app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        original_theme = app.state.theme_name
        await pilot.press("ctrl+t")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    assert app.state.theme_name == original_theme
