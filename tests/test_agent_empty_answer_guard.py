"""M214 (B2) / M254 — a turn must not finalize a blank answer on the first empty
round, and must not retry one it cannot win.

Regression guard for the production symptom: the agent ends a turn with no tool
calls and no text, the channel placeholder stays "...", and the real answer only
appears on the next user message.

M254 splits the two causes, which need opposite handling:

- `finish_reason="stop"` — the model finished and said nothing. A nudge is the
  right tool, and one was not enough (the 2026-09-17 report), so it is bounded
  at `_EMPTY_ANSWER_NUDGE_LIMIT` instead of fixed at a single try.
- `finish_reason="length"` — the completion budget ran out. For a reasoning
  model the visible answer is the tail of the budget, so it is what gets cut.
  Re-asking with the same budget hits the same wall, so the run reports
  `truncated` instead of burning another thinking round on a lost cause.
"""

from __future__ import annotations

from pathlib import Path

from tests.conftest import StubProvider
from veles.core.agent import Agent
from veles.core.memory import SessionStore
from veles.core.provider import ProviderResponse, TokenUsage
from veles.core.tools.registry import Registry


def _empty() -> ProviderResponse:
    return ProviderResponse(text=None, tool_calls=[], usage=TokenUsage(), finish_reason="stop")


def _truncated(reasoning: int = 31_900) -> ProviderResponse:
    """What a reasoning model returns when thinking ate the whole cap."""
    return ProviderResponse(
        text=None,
        tool_calls=[],
        usage=TokenUsage(completion_tokens=32_000, reasoning_tokens=reasoning),
        finish_reason="length",
    )


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


def test_a_second_nudge_can_still_win(tmp_path: Path):
    """M254: the original report was that one retry is not enough. A model that
    stays mute once and answers on the second ask now gets there."""
    store = SessionStore(str(tmp_path / "m.db"))
    try:
        provider = StubProvider([_empty(), _empty(), _text("finally")])
        result = _agent(provider, store).run("write the report")
        assert result.text == "finally"
        assert result.stopped_reason == "completed"
        assert len(provider.calls) == 3
    finally:
        store.close()


def test_persistently_empty_is_bounded(tmp_path: Path):
    """A model that will never speak must not be able to spend the whole
    iteration budget being asked to — bounded like the fenced parse nudge."""
    from veles.core.agent import _EMPTY_ANSWER_NUDGE_LIMIT

    store = SessionStore(str(tmp_path / "m.db"))
    try:
        provider = StubProvider([_empty()], repeat_last=True)
        result = _agent(provider, store).run("hi")
        assert result.text == ""
        assert result.stopped_reason == "empty"
        assert len(provider.calls) == _EMPTY_ANSWER_NUDGE_LIMIT + 1
    finally:
        store.close()


def test_a_truncated_answer_is_not_retried(tmp_path: Path):
    """The retry that M254 removes. `finish_reason="length"` means the cap was
    hit; asking again with the same cap truncates again, and for a reasoning
    model each attempt costs a full thinking round. Report it instead."""
    store = SessionStore(str(tmp_path / "m.db"))
    try:
        provider = StubProvider([_truncated()], repeat_last=True)
        result = _agent(provider, store).run("write the report")
        assert result.stopped_reason == "truncated"
        assert len(provider.calls) == 1  # no nudge round at all
        assert result.usage.reasoning_tokens == 31_900
    finally:
        store.close()


def test_truncation_does_not_mask_a_real_answer(tmp_path: Path):
    """A truncated response that still carries text is a completed turn — the
    new branch must only fire on an EMPTY one."""
    store = SessionStore(str(tmp_path / "m.db"))
    try:
        cut = ProviderResponse(
            text="partial answer",
            tool_calls=[],
            usage=TokenUsage(),
            finish_reason="length",
        )
        result = _agent(StubProvider([cut]), store).run("hi")
        assert result.stopped_reason == "completed"
        assert result.text == "partial answer"
    finally:
        store.close()
