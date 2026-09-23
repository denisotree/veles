"""M284: the agent's `ask_user` reaches a Telegram chat and waits for the answer.

The daemon answered every question with "no human available" (M148b), so an
agent in a chat could never ask for a detail only the user has. End to end: the
real gateway, the in-process backend, the runner's question prompter, and an
agent that calls the real `ask_user_question`. Only Telegram's HTTP is faked.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from veles.channels.in_process_backend import InProcessRunBackend
from veles.channels.session_map import SessionMap
from veles.channels.telegram import TelegramGateway
from veles.core.agent import RunResult
from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.daemon.auth import TokenStore
from veles.daemon.server import build_state


@dataclass
class _AskingAgent:
    session_id: str
    options: list[str] | None

    def run(self, prompt, *, on_text_delta=None, event_listener=None):
        from veles.core.user_prompt import ask_user_question

        answer = ask_user_question("Which colour?", self.options)
        text = f"painting it {answer}"
        if on_text_delta is not None:
            on_text_delta(text)
        return RunResult(text=text, iterations=1, session_id=self.session_id)


def _chat(tmp_path, options):
    project = init_project(tmp_path / "proj", name="proj")
    store = SessionStore(project.memory_db_path)

    def factory(session_id, *, prompt=None, **_kw):
        return _AskingAgent(session_id=session_id or store.create_session(), options=options)

    state = build_state(
        project=project,
        store=store,
        token_store=TokenStore.load(tmp_path / "t.json"),
        agent_factory=factory,
    )
    log: list[dict] = []

    async def fake_send(method, payload):
        log.append({"method": method, **payload})
        return {"message_id": len(log), "chat": payload.get("chat_id")}

    gw = TelegramGateway(
        bot_token="X",
        daemon_client=InProcessRunBackend(state),
        session_map=SessionMap.load(tmp_path / "tg.json"),
    )
    gw._telegram_send = fake_send  # type: ignore[method-assign]
    return gw, log, store


def _message(text: str) -> dict:
    return {"update_id": 1, "message": {"chat": {"id": 42, "type": "private"}, "text": text}}


async def _until(predicate, timeout: float = 5.0) -> None:
    for _ in range(int(timeout / 0.02)):
        if predicate():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("timed out waiting")


def _asked(log) -> list[dict]:
    return [e for e in log if "needs your input" in str(e.get("text", ""))]


async def _start_turn(gw) -> asyncio.Task:
    await gw._handle_update(_message("paint the fence"))
    return asyncio.create_task(gw._flush_buffer("42"))


async def test_a_typed_reply_answers_the_agents_question(tmp_path) -> None:
    gw, log, store = _chat(tmp_path, options=None)
    turn = await _start_turn(gw)
    await _until(lambda: _asked(log))
    assert "reply_markup" not in _asked(log)[0] or not _asked(log)[0]["reply_markup"]

    await gw._handle_update(_message("dark green"))  # the answer, not a new turn
    await asyncio.wait_for(turn, 5)
    finals = [e["text"] for e in log if "painting it" in str(e.get("text", ""))]
    assert finals and "painting it dark green" in finals[-1]
    # The question message now reads question → answer.
    edits = [e for e in log if e["method"] == "editMessageText" and "Which colour?" in e["text"]]
    assert edits and "dark green" in edits[-1]["text"]
    store.close()


async def test_a_button_tap_answers_with_the_options_label(tmp_path) -> None:
    gw, log, store = _chat(tmp_path, options=["Red", "Blue"])
    turn = await _start_turn(gw)
    await _until(lambda: _asked(log))
    keyboard = _asked(log)[0]["reply_markup"]["inline_keyboard"]
    assert [row[0]["text"] for row in keyboard] == ["Red", "Blue"]  # one option per row

    await gw._handle_callback_query(
        {
            "id": "cb1",
            "data": keyboard[1][0]["callback_data"],
            "from": {"id": 42},
            "message": {"chat": {"id": 42}, "message_id": 7},
        }
    )
    await asyncio.wait_for(turn, 5)
    assert any("painting it Blue" in str(e.get("text", "")) for e in log)
    store.close()


async def test_a_run_nobody_can_answer_is_not_kept_waiting(tmp_path) -> None:
    """An HTTP caller or a job has no one to ask: `ask_user` still returns "no
    human available" at once, instead of stalling for the prompt timeout."""
    gw, _, store = _chat(tmp_path, options=None)
    backend = gw.daemon_client
    payload = await backend.submit_run("paint", origin=None)
    state = backend._state  # type: ignore[attr-defined]
    await asyncio.wait_for(asyncio.gather(*state.run_tasks), 5)
    assert state.get_run(payload["run_id"]).final_text == "painting it None"
    store.close()


def test_an_unanswered_question_times_out_to_no_answer() -> None:
    from veles.daemon.channel_prompter import make_question_prompter
    from veles.daemon.runner import new_run_handle

    async def scenario() -> str | None:
        handle = new_run_handle()
        prompter = make_question_prompter(handle, asyncio.get_running_loop(), timeout=0.05)
        answer = await asyncio.to_thread(prompter, "Which colour?", None)
        await asyncio.sleep(0)
        assert handle.events[-1] == {
            "type": "prompt_resolved",
            "prompt_id": handle.events[0]["prompt_id"],
            "reason": "timeout",
        }
        assert handle.pending_prompts == {}
        return answer

    assert asyncio.run(scenario()) is None


@pytest.mark.parametrize("origin, asks", [("telegram:42", True), (None, False), ("local", False)])
def test_only_a_chat_origin_gets_questions(origin, asks) -> None:
    from veles.daemon.turns import asks_questions

    assert asks_questions(origin) is asks
