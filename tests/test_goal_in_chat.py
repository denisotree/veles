"""M280b: a goal runs in a Telegram chat.

End to end through the real gateway, the in-process backend and the production
GoalMode. Only the agent factory (which records what it was asked to build) and
Telegram's HTTP are fakes.
"""

from __future__ import annotations

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
class _Agent:
    session_id: str
    reply: str

    def run(self, prompt, *, on_text_delta=None, event_listener=None):
        if on_text_delta is not None:
            on_text_delta(self.reply)
        return RunResult(text=self.reply, iterations=1, session_id=self.session_id)


@pytest.fixture()
def calls() -> list[dict]:
    return []


@pytest.fixture()
def chat(tmp_path, calls):
    project = init_project(tmp_path / "proj", name="proj")
    store = SessionStore(project.memory_db_path)

    def factory(session_id, *, prompt=None, mode=None, extra_system=None, toolless=False):
        calls.append({"session_id": session_id, "mode": mode, "toolless": toolless})
        return _Agent(session_id=session_id, reply="What should hello.txt contain?")

    state = build_state(
        project=project,
        store=store,
        token_store=TokenStore.load(tmp_path / "t.json"),
        agent_factory=factory,
        default_model="stub/model",
    )
    sent: list[str] = []

    async def fake_send(method, payload):
        if payload.get("text"):
            sent.append(payload["text"])
        return {"message_id": 1, "chat": payload.get("chat_id")}

    smap = SessionMap.load(tmp_path / "tg.json")
    gw = TelegramGateway(bot_token="X", daemon_client=InProcessRunBackend(state), session_map=smap)
    gw._telegram_send = fake_send  # type: ignore[method-assign]
    yield gw, state, sent
    store.close()


def _message(text: str) -> dict:
    return {"update_id": 1, "message": {"chat": {"id": 42, "type": "private"}, "text": text}}


async def test_goal_command_starts_the_interview_in_this_chat(chat, calls) -> None:
    """A chat that never spoke: `/goal <task>` gets a session in goal mode, and
    GoalMode's interview asks its first question — with no tools in reach."""
    gw, state, sent = chat
    await gw._handle_update(_message("/goal create hello.txt"))

    sid = gw.session_map.get("42")
    assert sid is not None
    assert state.chat_mode(sid).mode == "goal"
    assert state.chat_mode(sid).active_goal_id  # GoalMode created the goal
    assert calls and calls[0]["toolless"] is True  # the interview gets no tools
    assert any("What should hello.txt contain?" in s for s in sent)


async def test_a_second_goal_command_does_not_start_another(chat, calls) -> None:
    gw, _, sent = chat
    await gw._handle_update(_message("/goal create hello.txt"))
    calls.clear()
    sent.clear()
    await gw._handle_update(_message("/goal something else"))
    assert calls == []
    assert any("already running" in s for s in sent)


async def test_goal_without_a_task_explains_itself(chat, calls) -> None:
    gw, _, sent = chat
    await gw._handle_update(_message("/goal"))
    assert calls == []
    assert any("/goal &lt;task&gt;" in s for s in sent)


async def test_post_v1_runs_rejects_an_unknown_mode(aiohttp_client, tmp_path) -> None:
    from veles.daemon.server import make_app

    project = init_project(tmp_path / "p2", name="p2")
    store = SessionStore(project.memory_db_path)
    tokens = TokenStore.load(tmp_path / "t2.json")
    tokens.add("default")
    state = build_state(
        project=project, store=store, token_store=tokens, agent_factory=lambda *a, **k: None
    )
    client = await aiohttp_client(make_app(state))
    resp = await client.post(
        "/v1/runs",
        json={"prompt": "x", "mode": "turbo"},
        headers={"Authorization": f"Bearer {tokens.list()[0].token}"},
    )
    assert resp.status == 400
    store.close()
