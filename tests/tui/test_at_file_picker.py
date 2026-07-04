"""M78: typing `@` after whitespace opens FilePickerScreen and inserts
the chosen path."""

from __future__ import annotations

from pathlib import Path

from veles.core.session_state import AppState
from veles.tui.app import TuiApp
from veles.tui.screens import FilePickerScreen
from veles.tui.widgets.composer import Composer


def _app(tmp_project, agent_factory_for, text_response) -> TuiApp:
    project, store = tmp_project
    return TuiApp(
        state=AppState(session_id=None, provider_name="openrouter", model="m"),
        agent_factory=agent_factory_for(text_response("ok")),
        project=project,
        store=store,
    )


def test_file_picker_lists_project_files(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("hi", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("hi", encoding="utf-8")
    screen = FilePickerScreen(tmp_path)
    # `_build_items` runs in __init__; the visible_labels list updates
    # on mount but we can read the underlying items directly.
    labels = [item.label for item in screen._items]
    assert "README.md" in labels
    assert "src/main.py" in labels


async def test_at_keypress_opens_picker(tmp_project, agent_factory_for, text_response) -> None:
    project, _ = tmp_project
    # Seed at least one project file so the picker has something to show.
    (project.root / "data.txt").write_text("x", encoding="utf-8")
    app = _app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        composer = pilot.app.query_one(Composer)
        composer.focus()
        await pilot.press("@")
        await pilot.pause()
        # FilePickerScreen should now be on top of the screen stack.
        assert any(isinstance(s, FilePickerScreen) for s in pilot.app.screen_stack)
        # Dismiss with Escape so we don't insert anything; the bare `@`
        # remains in the composer.
        await pilot.press("escape")
        await pilot.pause()
        assert composer.text == "@"


async def test_at_picker_inserts_path_after_at(
    tmp_project, agent_factory_for, text_response
) -> None:
    project, _ = tmp_project
    (project.root / "alpha.md").write_text("x", encoding="utf-8")
    app = _app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        composer = pilot.app.query_one(Composer)
        composer.focus()
        await pilot.press("@")
        await pilot.pause()
        # Filter to "alpha" then Enter picks the first match.
        await pilot.press("a", "l", "p", "h", "a")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert "@alpha.md" in composer.text


async def test_at_inside_word_does_not_open_picker(
    tmp_project, agent_factory_for, text_response
) -> None:
    """Typing `foo@bar.com` shouldn't open the picker — `@` must be at
    a word boundary."""
    app = _app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        composer = pilot.app.query_one(Composer)
        composer.focus()
        await pilot.press("f", "o", "o")
        await pilot.press("@")
        await pilot.pause()
        assert not any(isinstance(s, FilePickerScreen) for s in pilot.app.screen_stack)
        assert composer.text == "foo@"
