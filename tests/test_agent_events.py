"""Integration: Agent.run() emits typed events for each significant turn step.

Tier ε, M69 — wiring contract:
  user_message       on every user prompt
  assistant_message  on every model reply
  tool_call          on every dispatch attempt
  permission_decision on every sensitive-tool gate
  tool_result        on every dispatch completion (success or denial)
"""

from __future__ import annotations

from pathlib import Path

from tests.conftest import StubProvider as _StubProvider
from veles.core.agent import Agent
from veles.core.events import EventWriter, filter_events, read_events
from veles.core.permission.prompt import (
    PromptAnswer,
)
from veles.core.permission.prompt import (
    reset_prompter as reset_unified_prompter,
)
from veles.core.permission.prompt import (
    set_prompter as set_unified_prompter,
)
from veles.core.provider import ProviderResponse, TokenUsage, ToolCall
from veles.core.tools.registry import Registry, ToolEntry
from veles.core.trust import begin_trust_turn, end_trust_turn


def _final(text: str) -> ProviderResponse:
    return ProviderResponse(
        text=text,
        tool_calls=[],
        usage=TokenUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
        finish_reason="stop",
    )


def _tool(name: str, args: dict, call_id: str = "c1") -> ProviderResponse:
    return ProviderResponse(
        text=None,
        tool_calls=[ToolCall(id=call_id, name=name, arguments=args)],
        usage=TokenUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
        finish_reason="tool_use",
    )


def _registry_with_echo(sensitive: bool = False) -> Registry:
    reg = Registry()
    reg.register(
        ToolEntry(
            name="echo",
            description="Echo input",
            parameter_schema={"type": "object"},
            handler=lambda text="": f"echo:{text}",
            is_async=False,
            sensitive=sensitive,
        )
    )
    return reg


def test_emits_user_and_assistant_events(tmp_path: Path) -> None:
    provider = _StubProvider(responses=[_final("hi")])
    writer = EventWriter(tmp_path / "events.jsonl")
    agent = Agent(provider, Registry(), model="m", event_writer=writer)
    agent.run("ping")
    events = read_events(tmp_path / "events.jsonl")
    types = [e["type"] for e in events]
    assert types == ["user_message", "assistant_message"]
    assert filter_events(events, type_="user_message")[0]["text"] == "ping"
    assert filter_events(events, type_="assistant_message")[0]["text"] == "hi"


def test_emits_tool_call_and_tool_result(tmp_path: Path) -> None:
    provider = _StubProvider(responses=[_tool("echo", {"text": "x"}), _final("done")])
    writer = EventWriter(tmp_path / "events.jsonl")
    agent = Agent(provider, _registry_with_echo(), model="m", event_writer=writer)
    agent.run("hi")
    events = read_events(tmp_path / "events.jsonl")
    types = [e["type"] for e in events]
    # user → assistant(with tool call) → tool_call → tool_result → assistant(final)
    assert "tool_call" in types
    assert "tool_result" in types
    tc = filter_events(events, type_="tool_call")[0]
    tr = filter_events(events, type_="tool_result")[0]
    assert tc["name"] == "echo"
    assert tc["arguments"] == {"text": "x"}
    assert tr["output"] == "echo:x"
    assert tr["error"] is None


def test_emits_permission_decision_for_sensitive_tool(tmp_path: Path) -> None:
    """When a sensitive tool fires the trust ladder, we emit a
    permission_decision event with the actual outcome."""
    token = begin_trust_turn()
    pt = set_unified_prompter(lambda _req: PromptAnswer("allow_once"))
    try:
        provider = _StubProvider(responses=[_tool("echo", {"text": "x"}), _final("ok")])
        writer = EventWriter(tmp_path / "events.jsonl")
        agent = Agent(
            provider,
            _registry_with_echo(sensitive=True),
            model="m",
            event_writer=writer,
        )
        agent.run("hi")
        events = read_events(tmp_path / "events.jsonl")
        decisions = filter_events(events, type_="permission_decision")
        assert len(decisions) == 1
        assert decisions[0]["tool_name"] == "echo"
        assert decisions[0]["decision"] == "allow"
        assert decisions[0]["rule"] == "trust_ladder"
    finally:
        reset_unified_prompter(pt)
        end_trust_turn(token)


def test_emits_permission_decision_deny_on_refusal(tmp_path: Path) -> None:
    token = begin_trust_turn()
    pt = set_unified_prompter(lambda _req: PromptAnswer("deny"))
    try:
        provider = _StubProvider(responses=[_tool("echo", {"text": "x"}), _final("ok")])
        writer = EventWriter(tmp_path / "events.jsonl")
        agent = Agent(
            provider,
            _registry_with_echo(sensitive=True),
            model="m",
            event_writer=writer,
        )
        agent.run("hi")
        events = read_events(tmp_path / "events.jsonl")
        decisions = filter_events(events, type_="permission_decision")
        assert len(decisions) == 1
        assert decisions[0]["decision"] == "deny"
        # The denial still gets a tool_result event (with error set).
        tool_results = filter_events(events, type_="tool_result")
        assert len(tool_results) == 1
        assert "refused" in tool_results[0]["output"]
    finally:
        reset_unified_prompter(pt)
        end_trust_turn(token)


def test_no_events_when_no_writer_and_no_project(tmp_path: Path) -> None:
    """Backward compat: tests that don't set up a project / writer must
    keep observing zero side effects."""
    provider = _StubProvider(responses=[_final("hi")])
    agent = Agent(provider, Registry(), model="m")
    agent.run("hi")
    assert not (tmp_path / "events.jsonl").exists()


def test_event_writer_failure_does_not_break_run(tmp_path: Path) -> None:
    class _BadEventWriter:
        def write(self, event):
            raise OSError("disk full")

    provider = _StubProvider(responses=[_final("hi")])
    agent = Agent(
        provider,
        Registry(),
        model="m",
        event_writer=_BadEventWriter(),  # type: ignore[arg-type]
    )
    result = agent.run("hi")
    assert result.text == "hi"
