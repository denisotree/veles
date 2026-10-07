"""M284: the agent's `ask_user` waits for an answer only where someone can give one.

The daemon answered every question with "no human available" (M148b), so an
agent in a chat could never ask for a detail only the user has. Here: the
daemon's side — which runs get questions, and the prompter's timeout. The
chat end to end (a typed reply, a button tap) is tested with the Telegram
module in the extension registry.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from veles.core.agent import RunResult
from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.daemon.auth import TokenStore
from veles.daemon.in_process_backend import InProcessRunBackend
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


async def test_a_run_nobody_can_answer_is_not_kept_waiting(tmp_path) -> None:
    """An HTTP caller or a job has no one to ask: `ask_user` still returns "no
    human available" at once, instead of stalling for the prompt timeout."""
    project = init_project(tmp_path / "proj", name="proj")
    store = SessionStore(project.memory_db_path)

    def factory(session_id, *, prompt=None, **_kw):
        return _AskingAgent(session_id=session_id or store.create_session(), options=None)

    state = build_state(
        project=project,
        store=store,
        token_store=TokenStore.load(tmp_path / "t.json"),
        agent_factory=factory,
    )
    payload = await InProcessRunBackend(state).submit_run("paint", origin=None)
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


@pytest.mark.parametrize("origin, asks", [("fake:42", True), (None, False), ("local", False)])
def test_only_a_running_chat_origin_gets_questions(tmp_path, origin, asks) -> None:
    from veles.core.platforms import ChannelCaps
    from veles.daemon.turns import asks_questions

    state = build_state(
        project=init_project(tmp_path / "p", name="p"),
        store=None,  # type: ignore[arg-type]
        token_store=TokenStore.load(),
        agent_factory=lambda *a, **k: None,  # type: ignore[arg-type,return-value]
    )
    state.channel_caps["fake"] = ChannelCaps(asks_questions=True)
    assert asks_questions(state, origin) is asks
    assert asks_questions(state, "notrunning:1") is False


def test_asks_questions_reads_state_from_a_thread(tmp_path) -> None:
    """Workers run in `to_thread`/job threads; the answer comes from the daemon's
    state, not from the module registry ContextVar."""
    import threading

    from veles.core.platforms import ChannelCaps
    from veles.daemon.turns import asks_questions

    state = build_state(
        project=init_project(tmp_path / "p", name="p"),
        store=None,  # type: ignore[arg-type]
        token_store=TokenStore.load(),
        agent_factory=lambda *a, **k: None,  # type: ignore[arg-type,return-value]
    )
    state.channel_caps["fake"] = ChannelCaps(asks_questions=True)
    seen: list[bool] = []
    worker = threading.Thread(target=lambda: seen.append(asks_questions(state, "fake:1")))
    worker.start()
    worker.join()
    assert seen == [True]


@dataclass
class _GatedAgent:
    session_id: str

    def run(self, prompt, *, on_text_delta=None, event_listener=None):
        from veles.core.critical_ops import confirm_critical
        from veles.core.permission.prompt import PromptRequest, current_prompter

        prompter = current_prompter()
        assert prompter is not None
        answer = prompter(PromptRequest("run_shell", {"command": "ls"}, kind="approval"))
        critical = confirm_critical("delete notes.txt", "")
        return RunResult(
            text=f"{answer.decision} {critical}", iterations=1, session_id=self.session_id
        )


def _gated_state(tmp_path, *, caps):
    from veles.core.platforms import ChannelCaps

    project = init_project(tmp_path / "proj", name="proj")
    store = SessionStore(project.memory_db_path)

    def factory(session_id, *, prompt=None, **_kw):
        return _GatedAgent(session_id=session_id or store.create_session())

    state = build_state(
        project=project,
        store=store,
        token_store=TokenStore.load(tmp_path / "t.json"),
        agent_factory=factory,
    )
    state.channel_caps["mail"] = ChannelCaps(asks_questions=caps)
    return state, store


async def test_a_channel_that_cannot_ask_refuses_at_once(tmp_path) -> None:
    """Email can't show buttons: every prompt waited out the 300 s timeout."""
    state, store = _gated_state(tmp_path, caps=False)
    payload = await InProcessRunBackend(state).submit_run("go", origin="mail:a@b")
    await asyncio.wait_for(asyncio.gather(*state.run_tasks), 5)
    run = state.get_run(payload["run_id"])
    assert run is not None
    assert run.final_text == "deny False"
    notices = [e for e in run.events if e.get("type") == "notice"]
    assert len(notices) == 2 and all(not n["live"] for n in notices)
    assert not any(str(e.get("type", "")).endswith("_prompt") for e in run.events)
    store.close()


def test_an_http_run_still_gets_prompts(tmp_path) -> None:
    from veles.daemon.turns import refuses_prompts

    state, store = _gated_state(tmp_path, caps=False)
    assert refuses_prompts(state, None) is False  # the TUI answers over WebSocket
    assert refuses_prompts(state, "mail:x") is True
    assert refuses_prompts(state, "notrunning:x") is False
    store.close()
