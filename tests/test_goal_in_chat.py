"""M280b: a goal runs in a Telegram chat.

End to end through the real gateway, the in-process backend and the production
GoalMode. Only the agent factory (which records what it was asked to build) and
Telegram's HTTP are fakes.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from veles.channels.session_map import SessionMap
from veles.channels.telegram import TelegramGateway
from veles.core.agent import RunResult
from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.daemon.auth import TokenStore
from veles.daemon.in_process_backend import InProcessRunBackend
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


# ---- b2/b3: after the plan is confirmed the goal runs to its end ----


@pytest.fixture()
def full_goal(tmp_path, monkeypatch):
    """A chat whose agents play every GoalMode phase: the interview agrees on
    the goal, planning persists a plan (as the `create_plan` tool does), the
    executor does the step, the advisor (CHECK) says done."""
    from veles.core.plan_artifact import create_plan

    project = init_project(tmp_path / "proj", name="proj")
    store = SessionStore(project.memory_db_path)
    summary = "Create hello.txt containing hi. Done when hello.txt exists with hi."

    def factory(session_id, *, prompt=None, mode=None, extra_system=None, toolless=False):
        if toolless:
            reply = f"<ready>{summary}</ready>"
        elif mode == "planning":
            create_plan(project.state_dir, objective="hello", steps=["write hello.txt"])
            reply = "plan ready"
        else:
            reply = "wrote hello.txt"
        return _Agent(session_id=session_id, reply=reply)

    monkeypatch.setattr(
        "veles.core.tools.builtin.advisor.call_advisor",
        lambda body, **_kw: '{"verdict": "goal_reached", "reason": "hello.txt exists"}',
    )
    state = build_state(
        project=project,
        store=store,
        token_store=TokenStore.load(tmp_path / "t.json"),
        agent_factory=factory,
        default_model="stub/model",
    )
    log: list[tuple[str, str]] = []

    async def fake_send(method, payload):
        if payload.get("text"):
            log.append((method, payload["text"]))
        return {"message_id": 1, "chat": payload.get("chat_id")}

    smap = SessionMap.load(tmp_path / "tg.json")
    gw = TelegramGateway(bot_token="X", daemon_client=InProcessRunBackend(state), session_map=smap)
    gw._telegram_send = fake_send  # type: ignore[method-assign]
    yield gw, state, log, summary
    store.close()


async def test_confirming_the_plan_runs_the_goal_to_done_in_the_same_turn(full_goal) -> None:
    from veles.core.goal import read_goal

    gw, state, log, summary = full_goal
    await gw._handle_update(_message("/goal create hello.txt"))  # interview → confirm
    sid = gw.session_map.get("42")
    goal_id = state.chat_mode(sid).active_goal_id
    # The agreed summary became the goal's objective — not the placeholder.
    assert read_goal(state.project.state_dir, goal_id).objective == summary
    # The chat is asked to confirm the summary, without the FSM's marker.
    assert any(summary in text for _, text in log)
    assert not any("ready&gt;" in text or "<ready>" in text for _, text in log)

    log.clear()
    await gw._handle_update(_message("yes"))
    await gw._flush_buffer("42")

    texts = [text for _, text in log]
    final = texts[-1]
    assert "Goal done" in final
    progress = [t for t in texts[:-1] if t.startswith("<i>goal")]
    assert progress, f"no live progress before the result: {texts}"
    assert read_goal(state.project.state_dir, goal_id).status == "completed"
    assert state.chat_mode(sid).mode is None  # the chat is back on its default


async def test_a_goal_already_running_elsewhere_is_not_driven_twice(full_goal) -> None:
    import asyncio

    from veles.core.file_lock import file_lock
    from veles.core.goal import goals_dir, read_goal

    gw, state, log, _ = full_goal
    await gw._handle_update(_message("/goal create hello.txt"))
    sid = gw.session_map.get("42")
    goal_id = state.chat_mode(sid).active_goal_id
    lock = goals_dir(state.project.state_dir) / f"{goal_id}.lock"
    held = asyncio.Event()
    release = asyncio.Event()

    def hold() -> None:  # another holder of the lock, as `veles goal resume` would be
        with file_lock(lock):
            asyncio.run_coroutine_threadsafe(_set(held), loop)
            fut = asyncio.run_coroutine_threadsafe(release.wait(), loop)
            fut.result()

    async def _set(ev):
        ev.set()

    loop = asyncio.get_running_loop()
    holder = loop.run_in_executor(None, hold)
    await held.wait()
    log.clear()
    await gw._handle_update(_message("yes"))
    await gw._flush_buffer("42")
    release.set()
    await holder
    assert any("already running elsewhere" in text for _, text in log)
    assert read_goal(state.project.state_dir, goal_id).status == "active"


# ---- b4: /goal status, cancel, resume ----


async def test_goal_status_shows_the_chats_goal(full_goal) -> None:
    gw, _, log, summary = full_goal
    await gw._handle_update(_message("/goal create hello.txt"))
    log.clear()
    await gw._handle_update(_message("/goal"))
    status = log[-1][1]
    assert "confirm" in status and summary[:20] in status


async def test_goal_cancel_ends_it_and_the_next_goal_starts_fresh(full_goal) -> None:
    """After a cancel the chat is back on its default, and a new `/goal` must
    create a new goal — GoalMode never checks status, so without the liveness
    check it would have carried on with the cancelled one's phases."""
    from veles.core.goal import read_goal

    gw, state, log, _ = full_goal
    await gw._handle_update(_message("/goal create hello.txt"))
    sid = gw.session_map.get("42")
    first = state.chat_mode(sid).active_goal_id
    await gw._handle_update(_message("/goal cancel"))
    assert read_goal(state.project.state_dir, first).status == "cancelled"
    assert state.chat_mode(sid).mode is None
    assert "Goal cancelled" in log[-1][1]

    await gw._handle_update(_message("/goal write notes"))
    second = state.chat_mode(sid).active_goal_id
    assert second and second != first


async def test_a_cancel_during_the_run_stops_it_after_the_current_step(
    full_goal, monkeypatch
) -> None:
    """`/goal cancel` arrives while the goal drives itself (commands don't wait
    for the chat's turn). Simulated here by the step itself cancelling, which is
    what the drive observes either way: the status on disk."""
    from veles.core.goal import cancel, read_goal

    gw, state, log, _ = full_goal
    await gw._handle_update(_message("/goal create hello.txt"))
    sid = gw.session_map.get("42")
    goal_id = state.chat_mode(sid).active_goal_id

    def advisor_while_user_cancels(body, **_kw):
        cancel(state.project.state_dir, goal_id, reason="user")
        return '{"verdict": "step_ok_continue", "reason": "more"}'

    monkeypatch.setattr("veles.core.tools.builtin.advisor.call_advisor", advisor_while_user_cancels)
    log.clear()
    await gw._handle_update(_message("yes"))
    await gw._flush_buffer("42")
    assert "Goal cancelled" in log[-1][1]
    assert read_goal(state.project.state_dir, goal_id).status == "cancelled"


async def test_goal_resume_continues_a_stopped_goal(full_goal, monkeypatch) -> None:
    from veles.core.goal import read_goal

    gw, state, log, _ = full_goal
    monkeypatch.setattr(
        "veles.core.tools.builtin.advisor.call_advisor",
        lambda body, **_kw: "<advisor unavailable: no model>",
    )
    await gw._handle_update(_message("/goal create hello.txt"))
    sid = gw.session_map.get("42")
    goal_id = state.chat_mode(sid).active_goal_id
    await gw._handle_update(_message("yes"))
    await gw._flush_buffer("42")
    assert "Goal stopped" in log[-1][1]

    monkeypatch.setattr(
        "veles.core.tools.builtin.advisor.call_advisor",
        lambda body, **_kw: '{"verdict": "goal_reached", "reason": "done"}',
    )
    await gw._handle_update(_message("/goal resume"))
    assert "Goal done" in log[-1][1]
    assert read_goal(state.project.state_dir, goal_id).status == "completed"


async def test_delete_session_goal_over_http(aiohttp_client, full_goal) -> None:
    from veles.daemon.server import make_app

    gw, state, _, _ = full_goal
    state.token_store.add("default")
    client = await aiohttp_client(make_app(state))
    headers = {"Authorization": f"Bearer {state.token_store.list()[0].token}"}
    resp = await client.delete("/v1/sessions/nobody/goal", headers=headers)
    assert (await resp.json())["cancelled"] is None

    await gw._handle_update(_message("/goal create hello.txt"))
    sid = gw.session_map.get("42")
    resp = await client.delete(f"/v1/sessions/{sid}/goal", headers=headers)
    assert (await resp.json())["cancelled"]["id"]
    assert state.chat_goal(sid) is None


# ---- M282: a restart does not make a chat forget its goal ----


async def test_a_restarted_daemon_still_knows_the_chats_goal(full_goal) -> None:
    """The chat's mode and goal were in memory only: after a restart `/goal`
    said "no goal" and `/goal resume` pointed at the host. `build_state`
    reloads them from `chat_modes.json`."""
    gw, state, log, _ = full_goal
    await gw._handle_update(_message("/goal create hello.txt"))  # → confirm
    sid = gw.session_map.get("42")
    goal_id = state.chat_mode(sid).active_goal_id

    restarted = build_state(
        project=state.project,
        store=state.store,
        token_store=state.token_store,
        agent_factory=state.agent_factory,
        default_model="stub/model",
    )
    assert restarted.chat_mode(sid).mode == "goal"
    assert restarted.chat_mode(sid).active_goal_id == goal_id

    gw.daemon_client = InProcessRunBackend(restarted)
    await gw._handle_update(_message("yes"))  # the restarted daemon finishes it
    await gw._flush_buffer("42")
    assert "Goal done" in log[-1][1]
    # …and forgets it once it is over, on disk too.
    again = build_state(
        project=state.project,
        store=state.store,
        token_store=state.token_store,
        agent_factory=state.agent_factory,
    )
    assert again.chat_mode(sid).active_goal_id is None


def test_a_corrupt_chat_modes_file_starts_empty(tmp_path) -> None:
    from veles.daemon.state import load_chat_modes

    path = tmp_path / "chat_modes.json"
    path.write_text("{not json", encoding="utf-8")
    assert load_chat_modes(path) == {}
    path.write_text('{"s1": {"mode": "turbo", "active_goal_id": "g1"}}', encoding="utf-8")
    loaded = load_chat_modes(path)
    assert loaded["s1"].mode is None and loaded["s1"].active_goal_id == "g1"


# ---- M283: `[goal]` in config.toml sets a new goal's budget ----


def _write_goal_config(project, body: str) -> None:
    (project.state_dir / "config.toml").write_text(f"[goal]\n{body}\n", encoding="utf-8")


async def test_a_chat_goal_takes_the_projects_goal_budget(full_goal) -> None:
    """A goal from the REPL or a chat got 30 / $5 / 1 h whatever the project
    wanted; only `veles goal start` flags could change it."""
    from veles.core.goal import read_goal

    gw, state, _, _ = full_goal
    _write_goal_config(state.project, "max_steps = 7\nmax_cost_usd = 0.5")
    await gw._handle_update(_message("/goal create hello.txt"))
    goal = read_goal(
        state.project.state_dir, state.chat_mode(gw.session_map.get("42")).active_goal_id
    )
    assert (goal.budget.max_steps, goal.budget.max_cost_usd) == (7, 0.5)
    assert goal.budget.max_wall_time_s == 3600  # not set → built-in default


def test_a_bad_goal_setting_is_ignored_not_fatal(tmp_path, caplog) -> None:
    from veles.core.goal import GoalBudget, default_budget

    project = init_project(tmp_path / "p", name="p")
    _write_goal_config(project, 'max_steps = "lots"\nmax_cost_usd = -1\nmax_wall_time_s = 60')
    with caplog.at_level("WARNING"):
        budget = default_budget(project)
    assert budget == GoalBudget(max_wall_time_s=60)
    assert "max_steps" in caplog.text and "max_cost_usd" in caplog.text


def test_cli_flags_override_the_project_budget_one_by_one(tmp_path, monkeypatch) -> None:
    import argparse

    from veles.cli.commands.goal import _start
    from veles.core.goal import list_goals

    project = init_project(tmp_path / "p", name="p")
    _write_goal_config(project, "max_steps = 7\nmax_cost_usd = 0.5")
    monkeypatch.setattr("veles.cli.commands.goal._drive", lambda *a, **k: 0)
    args = argparse.Namespace(
        objective="x",
        done_when="y",
        scope=None,
        max_steps=3,  # given → wins
        max_cost_usd=None,  # omitted → [goal]
        max_wall_time_s=None,  # omitted, not in [goal] → built-in
    )
    assert _start(args, project) == 0
    (goal,) = list_goals(project.state_dir)
    assert (goal.budget.max_steps, goal.budget.max_cost_usd, goal.budget.max_wall_time_s) == (
        3,
        0.5,
        3600,
    )


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
