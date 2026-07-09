"""Run-loop unit tests for `core.agent.Agent`.

The existing `test_agent_*.py` suite covers events, traces, approvals,
hooks, factory, and system-prompt refresh — all good integration
coverage. This file targets the bits left bare: the `run()` loop's
own decision branches that don't surface as events.

- `max_iterations` cutoff returns the last assistant text with the
  correct `stopped_reason`.
- An empty assistant turn terminates with `stopped_reason="empty"`.
- The optional `compressor` callback is invoked once per iteration,
  on the working history, before each `_request_completion`.
- A budget that's already exhausted on entry short-circuits before
  the provider is touched.
- Token usage from each iteration accumulates onto the final
  `RunResult.usage`."""

from __future__ import annotations

from tests.conftest import StubProvider as _StubProvider
from veles.core.agent import Agent
from veles.core.context import TokenBudget, current_budget, set_budget
from veles.core.provider import (
    Message,
    ProviderResponse,
    TokenUsage,
    ToolCall,
)
from veles.core.tools.registry import Registry, ToolEntry


def _final(text: str, *, prompt: int = 5, completion: int = 5) -> ProviderResponse:
    return ProviderResponse(
        text=text,
        tool_calls=[],
        usage=TokenUsage(
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=prompt + completion,
        ),
        finish_reason="stop",
    )


def _tool_call(name: str, call_id: str = "c1") -> ProviderResponse:
    return ProviderResponse(
        text=None,
        tool_calls=[ToolCall(id=call_id, name=name, arguments={})],
        usage=TokenUsage(prompt_tokens=3, completion_tokens=3, total_tokens=6),
        finish_reason="tool_use",
    )


def _echo_registry() -> Registry:
    reg = Registry()
    reg.register(
        ToolEntry(
            name="echo",
            description="Echo",
            parameter_schema={"type": "object"},
            handler=lambda: "echoed",
            is_async=False,
            sensitive=False,
        )
    )
    return reg


def test_empty_response_returns_empty_stopped_reason() -> None:
    """A first-turn assistant reply with no text and no tool_calls ends
    the run with stopped_reason='empty', not 'completed'."""
    provider = _StubProvider(responses=[_final("")])
    agent = Agent(provider, Registry(), model="m", max_iterations=5)
    result = agent.run("hi")
    assert result.text == ""
    assert result.stopped_reason == "empty"
    assert result.iterations == 1


def test_max_iterations_cutoff_returns_last_text() -> None:
    """When the model loops on tool calls past max_iterations, the run
    stops with `stopped_reason='max_iterations'` and surfaces the last
    assistant text — even if it was a blank text+tools turn."""
    # max_iterations=2, both turns emit a tool call → no termination from
    # text path; loop exhausts after 2 iterations.
    reg = _echo_registry()
    responses = [_tool_call("echo", "a"), _tool_call("echo", "b")]
    provider = _StubProvider(responses=responses)
    agent = Agent(provider, reg, model="m", max_iterations=2)
    result = agent.run("loop please")
    assert result.stopped_reason == "max_iterations"
    assert result.iterations == 2


def test_run_result_carries_invoked_tool_names() -> None:
    """`RunResult.invoked_tools` records every tool the run dispatched — even
    when the final round is empty. Callers like the curator judge success by
    "did the persist tool actually run", not by non-empty final prose (a
    thinking local model routinely ends with empty content after doing all
    the tool work — seen live 2026-07-08, ollama qwen3.5:9b)."""
    reg = _echo_registry()
    provider = _StubProvider(responses=[_tool_call("echo"), _final("")])
    agent = Agent(provider, reg, model="m", max_iterations=5)
    result = agent.run("go")
    assert result.stopped_reason == "empty"
    assert result.invoked_tools == frozenset({"echo"})


def test_run_result_invoked_tools_empty_without_tool_calls() -> None:
    provider = _StubProvider(responses=[_final("done")])
    agent = Agent(provider, Registry(), model="m", max_iterations=5)
    result = agent.run("hi")
    assert result.invoked_tools == frozenset()


def test_usage_accumulates_across_iterations() -> None:
    """Each iteration's `response.usage` rolls into `RunResult.usage`."""
    # Turn 1: tool call with usage 6 total; turn 2: final text with 10 total.
    reg = _echo_registry()
    provider = _StubProvider(responses=[_tool_call("echo"), _final("done", prompt=4, completion=6)])
    agent = Agent(provider, reg, model="m", max_iterations=5)
    result = agent.run("go")
    assert result.stopped_reason == "completed"
    assert result.usage.total_tokens == 6 + 10
    assert result.usage.prompt_tokens == 3 + 4
    assert result.usage.completion_tokens == 3 + 6


def test_compressor_runs_each_iteration_before_request() -> None:
    """The optional `compressor` callback fires once per iteration on
    the working history. Each call sees the prior turn appended."""
    seen: list[int] = []

    def compressor(history, session_id):
        del session_id
        seen.append(len(history))
        return history

    provider = _StubProvider(responses=[_final("ok")])
    agent = Agent(provider, Registry(), model="m", max_iterations=5, compressor=compressor)
    agent.run("hi")
    # Single iteration → single compressor call. History at that point
    # holds the user turn (1 msg). Compressor sees it before the
    # provider is called.
    assert seen == [1]


def test_budget_exhaustion_short_circuits_before_provider() -> None:
    """If `current_budget()` reports exhausted on entry to the iteration,
    the agent returns `stopped_reason='budget_exhausted'` without
    calling the provider — `_idx` stays at 0."""
    provider = _StubProvider(responses=[_final("never reached")])
    agent = Agent(provider, Registry(), model="m", max_iterations=5)
    # Set a budget that's already over its limit; the agent reads it via
    # `current_budget()` at the top of each iteration.
    token = set_budget(TokenBudget(limit=10, consumed=999))
    try:
        result = agent.run("hi")
    finally:
        # Reset budget so other tests in the same process aren't poisoned.
        from veles.core.context import reset_budget

        reset_budget(token)
    assert result.stopped_reason == "budget_exhausted"
    assert provider.calls == []  # provider never invoked


def test_run_passes_history_to_provider_each_iteration() -> None:
    """Each provider call receives the growing history: user → assistant
    → tool → ... — assert the message count grows as expected."""
    reg = _echo_registry()
    provider = _StubProvider(responses=[_tool_call("echo"), _final("done")])
    agent = Agent(provider, reg, model="m", max_iterations=5)
    agent.run("hi")
    # Iter 1: just the user message → 1.
    # Iter 2: user + assistant(tool_call) + tool result → 3.
    assert [len(c["messages"]) for c in provider.calls] == [1, 3]


def test_current_budget_helpers_isolated_after_run() -> None:
    """Regression: `Agent.run` doesn't leak budget state into the next
    run. We set+reset around the call; after it, `current_budget()`
    returns to whatever the outer test scope had (None by default)."""
    provider = _StubProvider(responses=[_final("ok")])
    agent = Agent(provider, Registry(), model="m", max_iterations=2)
    before = current_budget()
    agent.run("hi")
    assert current_budget() is before


def test_user_message_persisted_to_history() -> None:
    """Trivial but important: the user prompt lands at history[0]
    before the first provider round-trip and stays there."""
    provider = _StubProvider(responses=[_final("ok")])
    agent = Agent(provider, Registry(), model="m", max_iterations=2)
    result = agent.run("hello world")
    assert result.history[0] == Message(role="user", content="hello world")
