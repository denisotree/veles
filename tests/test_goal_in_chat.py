"""M280b: a goal runs in a chat session — the daemon's side.

Driven through the in-process backend (what a channel gateway calls) and the
production GoalMode; only the agent factory is a fake. The chat end to end
(`/goal` and its replies in Telegram) is tested with the Telegram module in the
extension registry.
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

_ORIGIN = "fake:42"


@dataclass
class _Agent:
    session_id: str
    reply: str

    def run(self, prompt, *, on_text_delta=None, event_listener=None):
        if on_text_delta is not None:
            on_text_delta(self.reply)
        return RunResult(text=self.reply, iterations=1, session_id=self.session_id)


@pytest.fixture()
def full_goal(tmp_path, monkeypatch):
    """A daemon whose agents play every GoalMode phase: the interview agrees on
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
        return _Agent(session_id=session_id or store.create_session(), reply=reply)

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
    yield state
    store.close()


async def _turn(state, prompt: str, *, session_id=None, mode=None) -> str:
    """One chat turn, as a gateway submits it; returns the session id."""
    payload = await InProcessRunBackend(state).submit_run(
        prompt, session_id=session_id, origin=_ORIGIN, mode=mode
    )
    await asyncio.wait_for(asyncio.gather(*state.run_tasks), 5)
    return payload["session_id"]


async def test_delete_session_goal_over_http(aiohttp_client, full_goal) -> None:
    from veles.daemon.server import make_app

    state = full_goal
    state.token_store.add("default")
    client = await aiohttp_client(make_app(state))
    headers = {"Authorization": f"Bearer {state.token_store.list()[0].token}"}
    resp = await client.delete("/v1/sessions/nobody/goal", headers=headers)
    assert (await resp.json())["cancelled"] is None

    sid = await _turn(state, "create hello.txt", mode="goal")
    resp = await client.delete(f"/v1/sessions/{sid}/goal", headers=headers)
    assert (await resp.json())["cancelled"]["id"]
    assert state.chat_goal(sid) is None


# ---- M282: a restart does not make a chat forget its goal ----


async def test_a_restarted_daemon_still_knows_the_chats_goal(full_goal) -> None:
    """The chat's mode and goal were in memory only: after a restart `/goal`
    said "no goal" and `/goal resume` pointed at the host. `build_state`
    reloads them from `chat_modes.json`."""
    from veles.core.goal import read_goal

    state = full_goal
    sid = await _turn(state, "create hello.txt", mode="goal")  # → confirm
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

    await _turn(restarted, "yes", session_id=sid)  # the restarted daemon finishes it
    assert read_goal(state.project.state_dir, goal_id).status == "completed"
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

    state = full_goal
    _write_goal_config(state.project, "max_steps = 7\nmax_cost_usd = 0.5")
    sid = await _turn(state, "create hello.txt", mode="goal")
    goal = read_goal(state.project.state_dir, state.chat_mode(sid).active_goal_id)
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
