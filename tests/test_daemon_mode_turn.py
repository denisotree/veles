"""M280 a4: a daemon run can be driven by an agent mode.

`make_mode_turn` adapts the REPL's `ModeContext` to `run_agent_in_background`.
The production modes run here against a recording agent factory, and a fake
mode stands in where the contract's edges matter (synthetic results, a mode
that forgets its `TurnDone`, a goal that ends and hands the chat back).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest

from veles.core.agent import RunResult
from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.daemon.auth import TokenStore
from veles.daemon.mode_turn import make_mode_turn
from veles.daemon.runner import new_run_handle, run_agent_in_background
from veles.daemon.server import build_state


@dataclass
class _Resp:
    text: str


@dataclass
class _Provider:
    verdict: str = "direct"

    def create_message(self, *_a, **_kw):
        return _Resp(self.verdict)


@dataclass
class _Agent:
    session_id: str
    reply: str
    provider: _Provider = field(default_factory=_Provider)

    def run(self, prompt, *, on_text_delta=None, event_listener=None):
        if on_text_delta is not None:
            on_text_delta(self.reply)
        return RunResult(text=self.reply, iterations=1, session_id=self.session_id)


@pytest.fixture()
def calls() -> list[dict]:
    """What the agent factory was asked to build, in order."""
    return []


@pytest.fixture()
def state(tmp_path, calls):
    project = init_project(tmp_path / "proj", name="proj")
    store = SessionStore(project.memory_db_path)
    tokens = TokenStore.load(tmp_path / "tokens.json")

    def factory(session_id, *, prompt=None, mode=None, extra_system=None, toolless=False):
        calls.append({"session_id": session_id, "prompt": prompt, "mode": mode})
        return _Agent(session_id=session_id, reply=f"answer from {mode}")

    st = build_state(
        project=project,
        store=store,
        token_store=tokens,
        agent_factory=factory,
        default_model="stub/model",
    )
    yield st
    store.close()


async def _run(state, sid: str, prompt: str, **kw):
    handle = new_run_handle(session_id=sid)
    await run_agent_in_background(
        handle, turn=make_mode_turn(state, session_id=sid, prompt=prompt), prompt=prompt, **kw
    )
    # Events are appended via `call_soon_threadsafe`; read them the way a
    # channel does — until the terminal event lands — not the instant the
    # runner returns (that raced on CI).
    for _ in range(200):
        if any(e.get("type") in ("completed", "error") for e in handle.events):
            break
        await asyncio.sleep(0.01)
    return handle


def _events(handle, kind: str) -> list[dict]:
    return [e for e in handle.events if e.get("type") == kind]


async def test_a_writing_turn_builds_a_writing_agent_on_the_sessions_id(state, calls) -> None:
    state.set_chat_mode("s1", "writing")
    handle = await _run(state, "s1", "hi")
    assert calls == [{"session_id": "s1", "prompt": "hi", "mode": "writing"}]
    assert handle.state == "completed"
    assert handle.final_text == "answer from writing"
    assert _events(handle, "text_delta")[0]["delta"] == "answer from writing"


async def test_a_planning_turn_builds_a_planning_agent(state, calls) -> None:
    state.set_chat_mode("s1", "planning")
    handle = await _run(state, "s1", "design X")
    assert [c["mode"] for c in calls] == ["planning"]
    assert handle.final_text == "answer from planning"


async def test_auto_routes_and_says_so_as_a_notice(state, calls) -> None:
    """AutoMode's `[auto → direct]` is a `SystemLine`; a chat sees it as a
    `notice` event. Its scratch agent and the real one share the session."""
    state.set_chat_mode("s1", "auto")
    handle = await _run(state, "s1", "what is 2+2")
    assert [n["text"] for n in _events(handle, "notice")] == ["[auto → direct]"]
    assert {c["session_id"] for c in calls} == {"s1"}
    assert handle.final_text == "answer from auto"


class _FakeMode:
    """Posts what a GoalMode phase transition posts."""

    name = label = "fake"
    system_block = ""

    def __init__(self, *, finish: bool = True, set_mode: str | None = None) -> None:
        self.finish = finish
        self.set_mode = set_mode

    def run_turn(self, prompt, ctx) -> None:
        from veles.core.agent_events import ChatDelta, SystemLine, TurnDone

        ctx.post(ChatDelta(text="Confirm the plan? (yes/no)"))
        ctx.post(SystemLine(text="[goal: interview → confirm]"))
        if self.set_mode is not None:
            ctx.state.mode = self.set_mode
        if self.finish:
            raw = '{"verdict": "step_ok_continue"}'
            ctx.post(TurnDone(RunResult(text=raw, iterations=0, stopped_reason="synthetic")))


async def test_a_synthetic_turn_shows_what_it_streamed_and_skips_the_hooks(
    state, monkeypatch
) -> None:
    monkeypatch.setattr("veles.core.modes.get_mode", lambda _name: _FakeMode())
    hooked: list[RunResult] = []
    state.set_chat_mode("s1", "goal")
    handle = await _run(state, "s1", "yes", post_turn_hook=hooked.append)
    assert handle.state == "completed"
    assert handle.final_text == "Confirm the plan? (yes/no)"  # not the advisor's JSON
    assert [n["text"] for n in _events(handle, "notice")] == ["[goal: interview → confirm]"]
    assert hooked == []  # nothing was asked of the model — nothing to learn from


async def test_a_goal_that_ends_hands_the_chat_back_to_its_default(state, monkeypatch) -> None:
    """GoalMode sets `mode = "auto"` when a goal completes or is cancelled; for
    a chat that means its default, not AutoMode's classifier."""
    monkeypatch.setattr("veles.core.modes.get_mode", lambda _name: _FakeMode(set_mode="auto"))
    state.set_chat_mode("s1", "goal")
    await _run(state, "s1", "yes")
    assert state.chat_mode("s1").mode is None


async def test_a_mode_that_never_finishes_the_turn_is_an_error(state, monkeypatch) -> None:
    monkeypatch.setattr("veles.core.modes.get_mode", lambda _name: _FakeMode(finish=False))
    state.set_chat_mode("s1", "goal")
    handle = await _run(state, "s1", "yes")
    assert handle.state == "failed"
    assert "without a result" in (handle.error or "")


async def test_the_runner_takes_exactly_one_of_agent_or_turn(state) -> None:
    with pytest.raises(ValueError, match="exactly one"):
        await run_agent_in_background(new_run_handle(), prompt="x")
