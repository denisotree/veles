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


async def test_ctrl_c_ignores_selection_and_copies_last_reply(
    tmp_project, agent_factory_for, text_response, monkeypatch: pytest.MonkeyPatch
) -> None:
    """M185: Ctrl+C no longer copies the mouse selection — copying the
    selection is bound exclusively to ⌘C / Ctrl+Shift+C. Even with a live
    selection, Ctrl+C copies the last reply (M77) and arms the exit window."""
    captured: dict[str, str] = {}
    monkeypatch.setattr(
        "veles.tui.clipboard.copy_text",
        lambda text: captured.__setitem__("text", text) or True,
    )

    app = _app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        pilot.app.state.last_assistant_text = "the whole reply"
        pilot.app.screen.get_selected_text = lambda: "just this bit"  # type: ignore[method-assign]
        await pilot.press("ctrl+c")
        await pilot.pause()
        # Selection is ignored; the last reply is what landed on the clipboard.
        assert captured.get("text") == "the whole reply"
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


async def test_selection_alone_does_not_copy(
    tmp_project, agent_factory_for, text_response, monkeypatch: pytest.MonkeyPatch
) -> None:
    """M185: a bare drag-select must NOT copy. Drive the real `TextSelected`
    message the screen emits on mouse-release (with a real selection) and
    assert the clipboard was never touched — only ⌘C / Ctrl+Shift+C copy."""
    from textual import events

    from veles.tui.widgets.chat_log import ChatLog

    calls: list[str] = []
    monkeypatch.setattr("veles.tui.clipboard.copy_text", lambda text: calls.append(text) or True)
    app = _app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        chat = pilot.app.query_one(ChatLog)
        chat.append_assistant_delta("hello selectable world")
        chat.seal_assistant()
        await pilot.pause()
        pilot.app.screen.text_select_all()  # real selection
        await pilot.pause()
        pilot.app.screen.post_message(events.TextSelected())  # what MouseUp emits
        await pilot.pause()
    assert calls == [], "selection alone must not copy"


async def test_copy_selection_action_copies_via_native_clipboard(
    tmp_project, agent_factory_for, text_response, monkeypatch: pytest.MonkeyPatch
) -> None:
    """M185: ⌘C / Ctrl+Shift+C → `action_copy_selection` copies the active
    selection through the native clipboard and confirms."""
    captured: dict[str, str] = {}
    monkeypatch.setattr(
        "veles.tui.clipboard.copy_text",
        lambda text: captured.__setitem__("text", text) or True,
    )
    app = _app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        pilot.app.screen.get_selected_text = lambda: "selected chunk"  # type: ignore[method-assign]
        pilot.app.action_copy_selection()
        await pilot.pause()
        assert captured.get("text") == "selected chunk"


async def test_copy_selection_action_noop_without_selection(
    tmp_project, agent_factory_for, text_response, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    monkeypatch.setattr("veles.tui.clipboard.copy_text", lambda text: calls.append(text) or True)
    app = _app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        pilot.app.screen.get_selected_text = lambda: ""  # type: ignore[method-assign]
        pilot.app.action_copy_selection()
        await pilot.pause()
        assert calls == []


async def test_ctrl_shift_c_copies_selection(
    tmp_project, agent_factory_for, text_response, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Linux/Windows-canonical Ctrl+Shift+C is bound to copy the selection
    (drives the real key→binding→action path, not a direct call)."""
    captured: dict[str, str] = {}
    monkeypatch.setattr(
        "veles.tui.clipboard.copy_text",
        lambda text: captured.__setitem__("text", text) or True,
    )
    app = _app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        pilot.app.screen.get_selected_text = lambda: "linux selection"  # type: ignore[method-assign]
        await pilot.press("ctrl+shift+c")
        await pilot.pause()
        assert captured.get("text") == "linux selection"


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
