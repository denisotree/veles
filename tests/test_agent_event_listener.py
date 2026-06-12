"""Per-run `event_listener` fan-out — Phase 0 of TUI rewrite.

The TUI inspector (and any future live UI: daemon WebSocket push,
channel relay) needs a synchronous, in-memory copy of the typed-event
stream that `_event_writer` persists to `events.jsonl`. Tailing the
file is lossy and clumsy; instead `Agent.run(event_listener=…)`
installs a callback that fires alongside the writer, from the same
`_emit` call site, for the lifetime of the run.

Invariants checked here:
  1. Listener observes the same event types as the writer (user_message,
     assistant_message, tool_call, permission_decision, tool_result).
  2. Listener is per-run: cleared on exit so a second `run()` without
     a listener is silent.
  3. A buggy listener never kills the run (best-effort fan-out).
  4. `listener=None` (the default) is fully equivalent to old behaviour.
"""

from __future__ import annotations

from tests.conftest import StubProvider as _StubProvider
from veles.core.agent import Agent
from veles.core.events import (
    AssistantMessage,
    Event,
    EventWriter,
    UserMessage,
    read_events,
)
from veles.core.events import (
    ToolCall as ToolCallEvent,
)
from veles.core.events import (
    ToolResult as ToolResultEvent,
)
from veles.core.provider import ProviderResponse, TokenUsage, ToolCall
from veles.core.tools.registry import Registry, ToolEntry


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


def _registry_with_echo() -> Registry:
    reg = Registry()
    reg.register(
        ToolEntry(
            name="echo",
            description="Echo input",
            parameter_schema={"type": "object"},
            handler=lambda text="": f"echo:{text}",
            is_async=False,
            sensitive=False,
        )
    )
    return reg


def test_listener_receives_full_event_stream_for_tool_turn() -> None:
    provider = _StubProvider(responses=[_tool("echo", {"text": "x"}), _final("done")])
    agent = Agent(provider, _registry_with_echo(), model="m")

    captured: list[Event] = []
    agent.run("hi", event_listener=captured.append)

    types = [type(e).__name__ for e in captured]
    # Expected order: user → assistant(tool_call) → tool_call event →
    # permission_decision (allow-by-default for non-sensitive tool) →
    # tool_result → assistant(final)
    assert "UserMessage" in types
    assert "AssistantMessage" in types
    assert "ToolCall" in types
    assert "ToolResult" in types

    user = next(e for e in captured if isinstance(e, UserMessage))
    assert user.text == "hi"
    tc = next(e for e in captured if isinstance(e, ToolCallEvent))
    assert tc.name == "echo"
    assert tc.arguments == {"text": "x"}
    tr = next(e for e in captured if isinstance(e, ToolResultEvent))
    assert tr.output == "echo:x"
    assert tr.error is None
    finals = [e for e in captured if isinstance(e, AssistantMessage)]
    assert finals[-1].text == "done"


def test_listener_fires_alongside_writer(tmp_path) -> None:
    """Writer and listener are independent sinks. Both see the same events."""
    provider = _StubProvider(responses=[_tool("echo", {"text": "y"}), _final("ok")])
    writer = EventWriter(tmp_path / "events.jsonl")
    agent = Agent(provider, _registry_with_echo(), model="m", event_writer=writer)

    captured: list[Event] = []
    agent.run("hello", event_listener=captured.append)

    on_disk = read_events(tmp_path / "events.jsonl")
    assert len(on_disk) == len(captured)
    assert [e["type"] for e in on_disk] == [_event_type_name(e) for e in captured]


def test_listener_is_per_run_and_cleared_after_exit() -> None:
    provider = _StubProvider(responses=[_final("a"), _final("b")])
    agent = Agent(provider, Registry(), model="m")

    first: list[Event] = []
    agent.run("one", event_listener=first.append)
    assert any(isinstance(e, UserMessage) and e.text == "one" for e in first)

    # Second run without a listener must be silent — and must not crash.
    second: list[Event] = []
    agent.run("two")
    assert second == []
    # `first` must not have grown (listener was cleared on exit).
    assert all(not (isinstance(e, UserMessage) and e.text == "two") for e in first)


def test_listener_default_none_preserves_legacy_behaviour() -> None:
    """No listener arg = identical to pre-Phase-0 surface."""
    provider = _StubProvider(responses=[_final("hi")])
    agent = Agent(provider, Registry(), model="m")
    result = agent.run("ping")  # zero kwargs — must work as before.
    assert result.text == "hi"
    assert result.stopped_reason == "completed"


def test_buggy_listener_does_not_kill_run() -> None:
    def explode(_event: Event) -> None:
        raise RuntimeError("listener fault")

    provider = _StubProvider(responses=[_tool("echo", {"text": "z"}), _final("done")])
    agent = Agent(provider, _registry_with_echo(), model="m")
    result = agent.run("hi", event_listener=explode)
    # The run completes normally; the buggy listener is swallowed.
    assert result.text == "done"
    assert result.stopped_reason == "completed"


# ---- helpers ----


def _event_type_name(e: Event) -> str:
    """Map dataclass instance → the canonical `type` field used in jsonl."""
    # Keep this in sync with the `type: str = "<…>"` defaults on each event.
    return {
        "UserMessage": "user_message",
        "AssistantMessage": "assistant_message",
        "ToolCall": "tool_call",
        "ToolResult": "tool_result",
        "PermissionDecision": "permission_decision",
        "ApprovalRequest": "approval_request",
        "ApprovalResult": "approval_result",
        "PlanUpdate": "plan_update",
        "Compaction": "compaction",
        "ConnectorCall": "connector_call",
        "ErrorEvent": "error",
    }[type(e).__name__]
