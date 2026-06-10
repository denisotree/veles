"""Composer word/line editing shortcuts — cross-platform.

Covers M80-style word/line deletion + navigation aliases. Ctrl+ flavours
are routed by TextArea's built-in bindings; the Alt+ and Super+ flavours
are registered on Composer explicitly so macOS users get native muscle
memory and Windows/Linux users get VS Code-style Ctrl+Backspace etc.

`super+` (Cmd) is not dispatched by Textual's Pilot in headless tests, so
those bindings are checked structurally (presence in `Composer.BINDINGS`)
rather than functionally."""

from __future__ import annotations

from veles.tui.widgets.composer import Composer


def _bound_keys() -> dict[str, str]:
    """Map of `binding.key → binding.action` over every Composer binding."""
    return {b.key: b.action for b in Composer.BINDINGS}


# ---------------- structural registration ----------------


def test_alt_word_bindings_registered():
    keys = _bound_keys()
    assert keys["alt+backspace"] == "delete_word_left"
    assert keys["alt+delete"] == "delete_word_right"
    assert keys["alt+left"] == "cursor_word_left"
    assert keys["alt+right"] == "cursor_word_right"
    assert keys["alt+shift+left"] == "cursor_word_left(True)"
    assert keys["alt+shift+right"] == "cursor_word_right(True)"


def test_ctrl_word_bindings_registered():
    """Linux / Windows convention. Parallel to alt+backspace / alt+delete."""
    keys = _bound_keys()
    assert keys["ctrl+backspace"] == "delete_word_left"
    assert keys["ctrl+delete"] == "delete_word_right"


def test_super_line_bindings_registered():
    """macOS Cmd convention. Headless terminals can't dispatch super+, so
    we lock the registration here to catch regressions."""
    keys = _bound_keys()
    assert keys["super+backspace"] == "delete_to_start_of_line"
    assert keys["super+delete"] == "delete_to_end_of_line_or_delete_line"
    assert keys["super+left"] == "cursor_line_start"
    assert keys["super+right"] == "cursor_line_end"
    assert keys["super+shift+left"] == "cursor_line_start(True)"
    assert keys["super+shift+right"] == "cursor_line_end(True)"
    assert keys["super+z"] == "undo"
    assert keys["super+shift+z"] == "redo"


# ---------------- functional (Pilot dispatchable keys) ----------------


async def _mounted_composer(tmp_project, agent_factory_for, text_response):
    from veles.tui.app import TuiApp
    from veles.tui.state import AppState

    project, store = tmp_project
    app = TuiApp(
        state=AppState(session_id=None, provider_name="openrouter", model="m"),
        agent_factory=agent_factory_for(text_response("ok")),
        project=project,
        store=store,
    )
    return app


async def test_alt_backspace_deletes_word_left(
    tmp_project, agent_factory_for, text_response
):
    app = await _mounted_composer(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        composer = pilot.app.query_one(Composer)
        composer.focus()
        composer.text = "hello world foo"
        # Move cursor to end so the delete touches the trailing word.
        await pilot.press("end")
        await pilot.press("alt+backspace")
        await pilot.pause()
        assert composer.text == "hello world "


async def test_ctrl_backspace_deletes_word_left(
    tmp_project, agent_factory_for, text_response
):
    app = await _mounted_composer(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        composer = pilot.app.query_one(Composer)
        composer.focus()
        composer.text = "alpha beta gamma"
        await pilot.press("end")
        await pilot.press("ctrl+backspace")
        await pilot.pause()
        assert composer.text == "alpha beta "


async def test_alt_left_jumps_one_word(
    tmp_project, agent_factory_for, text_response
):
    app = await _mounted_composer(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        composer = pilot.app.query_one(Composer)
        composer.focus()
        composer.text = "alpha beta"
        await pilot.press("end")
        # After Alt+Left the cursor should sit at the start of "beta" (col 6).
        await pilot.press("alt+left")
        await pilot.pause()
        row, col = composer.cursor_location
        assert (row, col) == (0, 6)


async def test_ctrl_delete_removes_word_right(
    tmp_project, agent_factory_for, text_response
):
    app = await _mounted_composer(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        composer = pilot.app.query_one(Composer)
        composer.focus()
        composer.text = "alpha beta"
        await pilot.press("home")
        await pilot.press("ctrl+delete")
        await pilot.pause()
        # Word "alpha" gone; the trailing space may stay depending on
        # TextArea word-boundary semantics — just ensure "alpha" is gone
        # and "beta" survives.
        assert "alpha" not in composer.text
        assert "beta" in composer.text


async def test_home_end_navigation(tmp_project, agent_factory_for, text_response):
    app = await _mounted_composer(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        composer = pilot.app.query_one(Composer)
        composer.focus()
        composer.text = "abcdef"
        await pilot.press("end")
        await pilot.pause()
        assert composer.cursor_location == (0, 6)
        await pilot.press("home")
        await pilot.pause()
        assert composer.cursor_location == (0, 0)
