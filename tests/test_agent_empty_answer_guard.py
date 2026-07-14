"""M214 (B2) — a turn must not finalize a blank answer on the first empty round.

Regression guard for the production symptom: the agent ends a turn with no tool
calls and no text, the channel placeholder stays "...", and the real answer only
appears on the next user message. The loop now forces ONE tool-free answer round
before giving up, bounded so a genuinely mute model can't loop forever.
"""

from __future__ import annotations

from pathlib import Path

from tests.conftest import StubProvider
from veles.core.agent import Agent
from veles.core.memory import SessionStore
from veles.core.provider import ProviderResponse, TokenUsage
from veles.core.tools.registry import Registry


def _empty() -> ProviderResponse:
    return ProviderResponse(text=None, tool_calls=[], usage=TokenUsage())


def _text(msg: str) -> ProviderResponse:
    return ProviderResponse(text=msg, tool_calls=[], usage=TokenUsage())


def _agent(provider, store) -> Agent:
    return Agent(
        provider=provider,
        registry=Registry(),
        model="stub-model",
        max_iterations=5,
        store=store,
        session_id=store.create_session(),
    )


def test_empty_first_round_forces_answer(tmp_path: Path):
    store = SessionStore(str(tmp_path / "m.db"))
    try:
        provider = StubProvider([_empty(), _text("here is the report")])
        result = _agent(provider, store).run("write the report")
        assert result.text == "here is the report"
        assert result.stopped_reason == "completed"
        assert len(provider.calls) == 2  # empty round + forced answer round
    finally:
        store.close()


def test_persistently_empty_is_bounded(tmp_path: Path):
    """If the model stays mute even after the nudge, finalize as 'empty' — no
    infinite loop."""
    store = SessionStore(str(tmp_path / "m.db"))
    try:
        provider = StubProvider([_empty()], repeat_last=True)
        result = _agent(provider, store).run("hi")
        assert result.text == ""
        assert result.stopped_reason == "empty"
        assert len(provider.calls) == 2  # one retry only, then give up
    finally:
        store.close()
