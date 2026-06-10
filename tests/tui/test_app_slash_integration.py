"""End-to-end: slash commands typed into the Composer reach the
registry, mutate state, render into the ChatLog, and apply quit/clear
flags. Complements `test_slash_builtin.py` (which exercises handlers in
isolation) by verifying the App's `_dispatch_slash` plumbing.
"""

from __future__ import annotations

from veles.tui.app import TuiApp
from veles.tui.state import AppState
from veles.tui.widgets.chat_log import ChatLog
from veles.tui.widgets.composer import Composer


def _new_app(tmp_project, agent_factory_for, text_response, *, reply: str = "unused") -> TuiApp:
    project, store = tmp_project
    state = AppState(session_id=None, provider_name="stub", model="m")
    return TuiApp(
        state=state,
        agent_factory=agent_factory_for(text_response(reply)),
        project=project,
        store=store,
    )


async def _settle_idle(pilot, ticks: int = 80) -> None:
    for _ in range(ticks):
        await pilot.pause()
        if not pilot.app.state.busy:
            return


async def test_help_renders_into_chat_log(tmp_project, agent_factory_for, text_response):
    app = _new_app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        composer = pilot.app.query_one(Composer)
        composer.text = "/help"
        await pilot.press("enter")
        await pilot.pause()
        chat = pilot.app.query_one(ChatLog)
        systems = [t for role, t in chat.transcript if role == "system"]
        assert any("Slash commands:" in t for t in systems)


async def test_unknown_slash_renders_error(tmp_project, agent_factory_for, text_response):
    app = _new_app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        composer = pilot.app.query_one(Composer)
        composer.text = "/nope"
        await pilot.press("enter")
        await pilot.pause()
        chat = pilot.app.query_one(ChatLog)
        errors = [t for role, t in chat.transcript if role == "error"]
        assert any("unknown command" in t for t in errors)


async def test_quit_slash_exits(tmp_project, agent_factory_for, text_response):
    app = _new_app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        composer = pilot.app.query_one(Composer)
        composer.text = "/quit"
        await pilot.press("enter")
        await pilot.pause()
    assert app.return_value == 0


async def test_clear_drops_transcript_and_resets_session(
    tmp_project, agent_factory_for, text_response
):
    app = _new_app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        # Run one full turn so there's something to clear.
        composer = pilot.app.query_one(Composer)
        composer.text = "hello"
        await pilot.press("enter")
        await _settle_idle(pilot)
        chat = pilot.app.query_one(ChatLog)
        assert any(role == "user" for role, _ in chat.transcript)

        composer.text = "/clear"
        await pilot.press("enter")
        await pilot.pause()
        # After /clear, transcript holds only the system confirmation.
        roles = [role for role, _ in chat.transcript]
        assert roles == ["system"]
        assert pilot.app.state.session_id is None
        assert pilot.app.state.last_assistant_text is None


async def test_model_set_updates_status_bar(
    tmp_project, agent_factory_for, text_response
):
    app = _new_app(tmp_project, agent_factory_for, text_response)
    async with app.run_test() as pilot:
        composer = pilot.app.query_one(Composer)
        composer.text = "/model openai/gpt-4o"
        await pilot.press("enter")
        await pilot.pause()
        # Status bar refresh fires from `_apply_slash_result`.
        from veles.tui.widgets.status_bar import StatusBar

        status = pilot.app.query_one(StatusBar)
        # M107: the status bar strips a leading known-provider segment so
        # the actual provider (`stub` for these tests) shows through,
        # avoiding doubled prefixes when `state.model` is fully qualified.
        assert "stub/gpt-4o" in status.last_text


async def test_save_uses_last_assistant_text(
    tmp_project, agent_factory_for, text_response
):
    """`on_turn_done` mirrors the chat-log tail into
    `state.last_assistant_text`; `/save` then writes that to the wiki."""
    app = _new_app(tmp_project, agent_factory_for, text_response, reply="Hello\n\nWorld.")
    async with app.run_test() as pilot:
        composer = pilot.app.query_one(Composer)
        composer.text = "what's up?"
        await pilot.press("enter")
        await _settle_idle(pilot)
        last = pilot.app.state.last_assistant_text
        assert last and "Hello" in last

        composer.text = "/save hello-world"
        await pilot.press("enter")
        await pilot.pause()
        chat = pilot.app.query_one(ChatLog)
        systems = [t for role, t in chat.transcript if role == "system"]
        assert any("wiki/queries/hello-world.md" in t for t in systems)
