"""Characterization of `Agent._run_inner`: every way a turn can end, pinned as
(stopped_reason, iterations, text, invoked tools, history roles, persisted
roles, tools offered per provider call). Written before the loop was split
into phases (M294) so the split can be checked against the old behaviour."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import StubProvider
from veles.core.agent import EMPTY_ANSWER_NUDGE, Agent
from veles.core.cancel import CancelToken, reset_cancel_token, set_cancel_token
from veles.core.context import TokenBudget, reset_budget, set_budget
from veles.core.fenced_tools import FENCED_RESULT_HEADER
from veles.core.memory import SessionStore
from veles.core.provider import ProviderResponse, TokenUsage, ToolCall
from veles.core.stall_guard import STALL_NUDGE
from veles.core.tools.registry import Registry, ToolEntry


def _usage(total: int = 10) -> TokenUsage:
    return TokenUsage(prompt_tokens=total // 2, completion_tokens=total // 2, total_tokens=total)


def _text(text: str | None, *, finish: str = "stop", total: int = 10) -> ProviderResponse:
    return ProviderResponse(text=text, tool_calls=[], usage=_usage(total), finish_reason=finish)


def _call(arg: str = "a", call_id: str = "c1", total: int = 10) -> ProviderResponse:
    return ProviderResponse(
        text=None,
        tool_calls=[ToolCall(id=call_id, name="echo", arguments={"x": arg})],
        usage=_usage(total),
        finish_reason="tool_use",
    )


def _registry() -> Registry:
    reg = Registry()
    reg.register(
        ToolEntry(
            name="echo",
            description="Echo",
            parameter_schema={"type": "object", "properties": {"x": {"type": "string"}}},
            handler=lambda x="": f"echo {x}",
            is_async=False,
            sensitive=False,
        )
    )
    return reg


def _run(tmp_path: Path, provider: StubProvider, **agent_kw):
    store = SessionStore(tmp_path / "memory.db")
    agent = Agent(
        provider=provider,
        registry=_registry(),
        model="m",
        system_prompt="sys",
        store=store,
        **agent_kw,
    )
    result = agent.run("hi")
    persisted = [m.role for m in store.load_messages(result.session_id)]
    offered = [c["tools"] is not None for c in provider.calls]
    return result, persisted, offered


def _roles(result) -> list[str]:
    return [m.role for m in result.history]


def test_plain_answer_completes_in_one_round(tmp_path: Path) -> None:
    result, persisted, offered = _run(tmp_path, StubProvider([_text("done")]))
    assert (result.stopped_reason, result.iterations, result.text) == ("completed", 1, "done")
    assert result.invoked_tools == frozenset()
    assert _roles(result) == persisted == ["system", "user", "assistant"]
    assert offered == [True]


def test_tool_round_then_answer(tmp_path: Path) -> None:
    result, persisted, offered = _run(tmp_path, StubProvider([_call(), _text("done")]))
    assert (result.stopped_reason, result.iterations, result.text) == ("completed", 2, "done")
    assert result.invoked_tools == frozenset({"echo"})
    assert _roles(result) == persisted == ["system", "user", "assistant", "tool", "assistant"]
    assert result.history[3].content == "echo a"
    assert offered == [True, True]
    assert result.usage.total_tokens == 20


def test_max_iterations_returns_last_assistant_text(tmp_path: Path) -> None:
    provider = StubProvider(
        [
            ProviderResponse(
                text="working",
                tool_calls=[ToolCall(id="c1", name="echo", arguments={"x": "1"})],
                usage=_usage(),
                finish_reason="tool_use",
            ),
            _call("2"),
        ]
    )
    result, persisted, _ = _run(tmp_path, provider, max_iterations=2, stall_repeat_limit=None)
    assert (result.stopped_reason, result.iterations, result.text) == (
        "max_iterations",
        2,
        "working",
    )
    assert _roles(result) == persisted


def test_empty_answers_are_nudged_then_end_empty(tmp_path: Path) -> None:
    from veles.core.agent import _EMPTY_ANSWER_NUDGE_LIMIT

    provider = StubProvider([_text(None)], repeat_last=True)
    result, persisted, offered = _run(tmp_path, provider)
    assert result.stopped_reason == "empty"
    assert result.iterations == 1 + _EMPTY_ANSWER_NUDGE_LIMIT
    nudges = [m for m in result.history if m.role == "user" and m.content == EMPTY_ANSWER_NUDGE]
    assert len(nudges) == _EMPTY_ANSWER_NUDGE_LIMIT
    # The nudge withholds tools for the round that follows it.
    assert offered == [True] + [False] * _EMPTY_ANSWER_NUDGE_LIMIT
    assert _roles(result) == persisted


def test_empty_answer_at_token_cap_is_truncated_without_nudge(tmp_path: Path) -> None:
    result, persisted, offered = _run(tmp_path, StubProvider([_text(None, finish="length")]))
    assert (result.stopped_reason, result.iterations, result.text) == ("truncated", 1, "")
    assert offered == [True]
    assert _roles(result) == persisted == ["system", "user", "assistant"]


def test_exhausted_budget_stops_before_the_provider(tmp_path: Path) -> None:
    token = set_budget(TokenBudget(limit=10, consumed=10))
    try:
        provider = StubProvider([_text("never")])
        result, persisted, _ = _run(tmp_path, provider)
    finally:
        reset_budget(token)
    assert (result.stopped_reason, result.iterations) == ("budget_exhausted", 0)
    assert result.text == "<budget exhausted: 10/10 tokens>"
    assert provider.calls == []
    assert persisted == ["system", "user"]


def test_budget_runs_out_mid_turn(tmp_path: Path) -> None:
    token = set_budget(TokenBudget(limit=15))
    try:
        result, _, _ = _run(tmp_path, StubProvider([_call(), _call("b"), _text("x")]))
    finally:
        reset_budget(token)
    assert (result.stopped_reason, result.iterations) == ("budget_exhausted", 2)
    assert result.invoked_tools == frozenset({"echo"})


def test_cancelled_turn(tmp_path: Path) -> None:
    cancel = CancelToken()
    cancel.cancel()
    token = set_cancel_token(cancel)
    try:
        result, _, _ = _run(tmp_path, StubProvider([_text("never")]))
    finally:
        reset_cancel_token(token)
    assert (result.stopped_reason, result.iterations, result.text) == ("cancelled", 0, "")


def test_stall_forces_one_tool_free_round(tmp_path: Path) -> None:
    provider = StubProvider([_call(), _call(), _call(), _text("answer")])
    result, persisted, offered = _run(tmp_path, provider, stall_repeat_limit=3)
    assert (result.stopped_reason, result.iterations, result.text) == ("completed", 4, "answer")
    assert offered == [True, True, True, False]
    assert [m.content for m in result.history if m.content == STALL_NUDGE] == [STALL_NUDGE]
    assert _roles(result) == persisted


def test_token_warning_is_injected_once(tmp_path: Path) -> None:
    provider = StubProvider([_call("1", total=30), _call("2", total=30), _text("done")])
    result, _, offered = _run(tmp_path, provider, token_warn_threshold=25)
    warnings = [m for m in result.history if m.role == "user" and "tokens" in (m.content or "")]
    assert len(warnings) == 1
    assert offered == [True, True, True]  # a warning never withholds tools
    assert result.stopped_reason == "completed"


def test_fenced_parse_error_is_fed_back(tmp_path: Path) -> None:
    broken = "```veles-tool\n{not json\n```"
    good = '```veles-tool\n{"name": "echo", "arguments": {"x": "f"}}\n```'
    provider = StubProvider([_text(broken), _text(good), _text("done")], supports_tools=False)
    result, persisted, offered = _run(tmp_path, provider)
    assert (result.stopped_reason, result.iterations, result.text) == ("completed", 3, "done")
    assert result.invoked_tools == frozenset({"echo"})
    assert offered == [False, False, False]  # fenced: tools live in the prompt
    fenced_results = [m for m in result.history if FENCED_RESULT_HEADER in (m.content or "")]
    assert len(fenced_results) == 1 and "echo f" in (fenced_results[0].content or "")
    assert _roles(result) == persisted
    assert "veles-tool" in (result.history[0].content or "")


@pytest.mark.parametrize("stream", [False, True])
def test_streaming_and_blocking_paths_agree(tmp_path: Path, stream: bool) -> None:
    from veles.core.provider import StreamEnd, TextDelta

    provider = StubProvider(
        [_text("done")],
        supports_streaming=stream,
        stream_events=[TextDelta(text="done"), StreamEnd(response=_text("done"))],
    )
    store = SessionStore(tmp_path / "memory.db")
    agent = Agent(provider=provider, registry=_registry(), model="m", store=store)
    seen: list[str] = []
    result = agent.run("hi", on_text_delta=seen.append if stream else None)
    assert (result.stopped_reason, result.iterations, result.text) == ("completed", 1, "done")
    assert provider.calls[0]["stream"] is stream
