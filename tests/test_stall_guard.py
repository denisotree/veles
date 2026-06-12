"""M144: stall/loop guard.

The Veles loop ends as soon as the model stops calling tools, so the only
stall it can fall into is calling the *same tool with the same arguments*
round after round. `StallGuard` detects that; the agent reacts by forcing one
tool-free round so the model must answer instead of looping the dead call.

Invariants:
  1. The same signature repeated `repeat_limit` times trips the guard once.
  2. Distinct signatures (different args) never trip it.
  3. `repeat_limit=None`/0 disables it; empty tool calls are ignored.
  4. End-to-end: a model stuck on one tool is forced to answer and the run
     terminates well before `max_iterations`, without the dead tool running
     `max_iterations` times.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from veles.core.agent import Agent
from veles.core.provider import (
    ProviderResponse,
    TokenUsage,
    ToolCall,
)
from veles.core.stall_guard import STALL_NUDGE, StallGuard, signature
from veles.core.tools.registry import Registry, ToolEntry


def _usage() -> TokenUsage:
    return TokenUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10)


def _call(name: str, args: dict, call_id: str = "c1") -> ToolCall:
    return ToolCall(id=call_id, name=name, arguments=args)


# --- unit: StallGuard ------------------------------------------------------


def test_same_signature_trips_once_at_repeat_limit() -> None:
    guard = StallGuard(repeat_limit=3)
    calls = [_call("read_file", {"path": "a.py"})]
    assert guard.record(calls) is False  # 1st
    assert guard.record(calls) is False  # 2nd
    assert guard.record(calls) is True  # 3rd — trips
    assert guard.record(calls) is False  # already tripped, stays quiet
    assert guard.tripped is True


def test_distinct_signatures_never_trip() -> None:
    guard = StallGuard(repeat_limit=3)
    for i in range(6):
        assert guard.record([_call("read_file", {"path": f"f{i}.py"})]) is False
    assert guard.tripped is False


def test_argument_order_does_not_change_signature() -> None:
    a = signature([_call("t", {"x": 1, "y": 2})])
    b = signature([_call("t", {"y": 2, "x": 1})])
    assert a == b


def test_disabled_and_empty_calls_are_noops() -> None:
    disabled = StallGuard(repeat_limit=None)
    calls = [_call("read_file", {"path": "a.py"})]
    for _ in range(10):
        assert disabled.record(calls) is False
    assert disabled.tripped is False

    zero = StallGuard(repeat_limit=0)
    for _ in range(10):
        assert zero.record(calls) is False

    guard = StallGuard(repeat_limit=2)
    assert guard.record([]) is False
    assert guard.record([]) is False
    assert guard.tripped is False


# --- integration: Agent ----------------------------------------------------


@dataclass
class _StuckProvider:
    """Calls the same tool forever while tools are offered; the moment the
    agent withholds tools (the forced answer round) it returns a real answer.
    `with_tools_calls` counts how many times tools were actually offered."""

    name: str = "stub"
    supports_tools: bool = True
    supports_streaming: bool = False
    with_tools_calls: int = 0
    tools_seen: list[bool] = field(default_factory=list)

    def create_message(self, messages, tools=None, *, model, max_tokens=4096):
        del messages, model, max_tokens
        self.tools_seen.append(bool(tools))
        if tools:
            self.with_tools_calls += 1
            return ProviderResponse(
                text=None,
                tool_calls=[_call("noop", {"x": 1}, call_id=f"c{self.with_tools_calls}")],
                usage=_usage(),
                finish_reason="tool_use",
            )
        return ProviderResponse(
            text="final answer after being unstuck",
            tool_calls=[],
            usage=_usage(),
            finish_reason="stop",
        )


def _registry_with_noop() -> Registry:
    reg = Registry()
    reg.register(
        ToolEntry(
            name="noop",
            description="Does nothing",
            parameter_schema={"type": "object"},
            handler=lambda **_: "ok",
            is_async=False,
            sensitive=False,
        )
    )
    return reg


def test_agent_forces_answer_when_tool_call_repeats() -> None:
    provider = _StuckProvider()
    agent = Agent(
        provider,
        _registry_with_noop(),
        model="m",
        max_iterations=30,
        stall_repeat_limit=3,
    )
    result = agent.run("do the thing")

    # Terminated with the forced answer, nowhere near max_iterations.
    assert result.text == "final answer after being unstuck"
    assert result.stopped_reason == "completed"
    assert result.iterations < 10
    # Tools were offered exactly 3 times (the stall threshold), then withheld.
    assert provider.with_tools_calls == 3
    assert provider.tools_seen[-1] is False  # last round was tool-free
    # The nudge was injected into history before the forced round.
    assert any(m.role == "user" and m.content == STALL_NUDGE for m in result.history)


def test_agent_unaffected_when_guard_disabled_and_tools_progress() -> None:
    # A provider that calls noop once then answers must be untouched by the guard.
    @dataclass
    class _OneToolProvider:
        name: str = "stub"
        supports_tools: bool = True
        supports_streaming: bool = False
        n: int = 0

        def create_message(self, messages, tools=None, *, model, max_tokens=4096):
            del messages, tools, model, max_tokens
            self.n += 1
            if self.n == 1:
                return ProviderResponse(
                    text=None,
                    tool_calls=[_call("noop", {"x": 1})],
                    usage=_usage(),
                    finish_reason="tool_use",
                )
            return ProviderResponse(
                text="done", tool_calls=[], usage=_usage(), finish_reason="stop"
            )

    agent = Agent(_OneToolProvider(), _registry_with_noop(), model="m")
    result = agent.run("go")
    assert result.text == "done"
    assert result.stopped_reason == "completed"
    assert not any(m.content == STALL_NUDGE for m in result.history)
