"""M77: Ctrl+C copy + double-tap exit, Ctrl+V text/image paste."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.tui.app import TuiApp
from veles.tui.state import AppState
from veles.tui.widgets.composer import Composer


def _app(tmp_project, agent_factory_for, text_response) -> TuiApp:
    project, store = tmp_project
    return TuiApp(
        state=AppState(session_id=None, provider_name="openrouter", model="m"),
        agent_factory=agent_factory_for(text_response("ok")),
        project=project,
        store=store,
    )


async def test_first_ctrl_c_copies_and_warns(
    tmp_project, agent_factory_for, text_response, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, str] = {}

    def fake_copy(text: str) -> bool:
        captured["text"] = text
        return True

    monkeypatch.setattr("veles.tui.clipboard.copy_text", fake_copy)

    app = _app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        pilot.app.state.last_assistant_text = "hello world"
        await pilot.press("ctrl+c")
        await pilot.pause()
    assert captured.get("text") == "hello world"


async def test_ctrl_c_copies_active_selection_over_last_reply(
    tmp_project, agent_factory_for, text_response, monkeypatch: pytest.MonkeyPatch
) -> None:
    """M183b: a live mouse text-selection takes priority over the last-reply
    copy, and the press is not treated as an exit intent."""
    captured: dict[str, str] = {}
    monkeypatch.setattr(
        "veles.tui.clipboard.copy_text",
        lambda text: captured.__setitem__("text", text) or True,
    )

    app = _app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        pilot.app.state.last_assistant_text = "the whole reply"
        # Simulate an in-app text selection on the active screen.
        pilot.app.screen.get_selected_text = lambda: "just this bit"  # type: ignore[method-assign]
        await pilot.press("ctrl+c")
        await pilot.pause()
        # Copied the selection, not the last reply; app still running.
        assert captured.get("text") == "just this bit"
        assert pilot.app.return_code is None


async def test_ctrl_c_without_selection_copies_last_reply(
    tmp_project, agent_factory_for, text_response, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No selection → fall back to the M77 last-reply copy."""
    captured: dict[str, str] = {}
    monkeypatch.setattr(
        "veles.tui.clipboard.copy_text",
        lambda text: captured.__setitem__("text", text) or True,
    )
    app = _app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        pilot.app.state.last_assistant_text = "the whole reply"
        pilot.app.screen.get_selected_text = lambda: ""  # type: ignore[method-assign]
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert captured.get("text") == "the whole reply"


async def test_screen_selection_extracts_chat_text(
    tmp_project, agent_factory_for, text_response
) -> None:
    """The selection machinery actually extracts text from a Markdown-sealed
    chat message (the real path a mouse drag drives). Proven via the Screen's
    own `text_select_all` so it doesn't depend on a synthetic drag — if this
    holds, a real drag's `get_selected_text()` returns the dragged substring
    and Ctrl+C copies it."""
    from veles.tui.widgets.chat_log import ChatLog

    app = _app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        chat = pilot.app.query_one(ChatLog)
        chat.append_assistant_delta("hello selectable world")
        chat.seal_assistant()  # re-renders through rich Markdown
        await pilot.pause()
        pilot.app.screen.text_select_all()
        await pilot.pause()
        selected = pilot.app.screen.get_selected_text() or ""
        assert "hello selectable world" in selected


async def test_double_ctrl_c_exits(
    tmp_project, agent_factory_for, text_response, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("veles.tui.clipboard.copy_text", lambda _t: False)
    app = _app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        pilot.app.state.last_assistant_text = "x"
        await pilot.press("ctrl+c")
        await pilot.pause()
        await pilot.press("ctrl+c")
        await pilot.pause()
    # App should have exited cleanly.
    assert pilot.app.return_code == 0


async def test_ctrl_v_pastes_text_into_composer(
    tmp_project, agent_factory_for, text_response, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("veles.tui.clipboard.paste_image", lambda _p: False)
    monkeypatch.setattr("veles.tui.clipboard.paste_text", lambda: "pasted text")

    app = _app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        composer = pilot.app.query_one(Composer)
        composer.focus()
        await pilot.press("ctrl+v")
        await pilot.pause()
        assert "pasted text" in composer.text


async def test_ctrl_v_image_paste_saves_to_veles_tmp_and_inserts_ref(
    tmp_project, agent_factory_for, text_response, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the clipboard holds an image, the app saves it into
    `<.veles/tmp/paste/>` and inserts an `@<rel>` reference."""

    def fake_image(target: Path) -> bool:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"\x89PNG\r\n\x1a\nfake")
        return True

    monkeypatch.setattr("veles.tui.clipboard.paste_image", fake_image)
    # Make sure text paste isn't taken if image succeeded.
    monkeypatch.setattr("veles.tui.clipboard.paste_text", lambda: pytest.fail("should not run"))

    app = _app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        composer = pilot.app.query_one(Composer)
        composer.focus()
        await pilot.press("ctrl+v")
        await pilot.pause()
        assert ".veles/tmp/paste/" in composer.text
        assert composer.text.startswith("@.veles/tmp/paste/")


async def test_ctrl_v_no_clipboard_content_is_noop(
    tmp_project, agent_factory_for, text_response, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("veles.tui.clipboard.paste_image", lambda _p: False)
    monkeypatch.setattr("veles.tui.clipboard.paste_text", lambda: None)

    app = _app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        composer = pilot.app.query_one(Composer)
        composer.focus()
        before = composer.text
        await pilot.press("ctrl+v")
        await pilot.pause()
        assert composer.text == before
