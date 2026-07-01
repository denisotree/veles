"""Tool_call ↔ tool_result pairing repair before a provider call.

The provider rejects an assistant `tool_call` with no matching tool result
("No tool output found for function call ...") or an orphaned tool result.
Compression / truncation / resume / a provider quirk can split a pair;
`repair_tool_pairing` makes the history self-consistent on the wire.
"""

from __future__ import annotations

from veles.core.history_repair import _PLACEHOLDER, repair_tool_pairing
from veles.core.provider import Message, ToolCall


def _asst(*calls: tuple[str, str], content: str | None = None) -> Message:
    return Message(
        role="assistant",
        content=content,
        tool_calls=[ToolCall(id=cid, name=name, arguments={}) for cid, name in calls],
    )


def _tool(call_id: str, content: str = "ok") -> Message:
    return Message(role="tool", content=content, tool_call_id=call_id)


def test_consistent_history_returned_unchanged() -> None:
    history = [
        Message(role="user", content="go"),
        _asst(("c1", "search")),
        _tool("c1"),
    ]
    assert repair_tool_pairing(history) is history  # same object → no allocation


def test_unanswered_tool_call_gets_placeholder() -> None:
    history = [
        Message(role="user", content="go"),
        _asst(("c1", "search")),  # no tool result follows → the 400 case
    ]
    out = repair_tool_pairing(history)
    assert len(out) == 3
    assert out[2].role == "tool" and out[2].tool_call_id == "c1"
    assert out[2].content == _PLACEHOLDER
    # every call now has a result
    call_ids = {tc.id for m in out for tc in m.tool_calls}
    result_ids = {m.tool_call_id for m in out if m.role == "tool"}
    assert call_ids <= result_ids


def test_orphaned_tool_result_dropped() -> None:
    history = [
        Message(role="user", content="go"),
        _tool("ghost"),  # no assistant tool_call references "ghost"
        Message(role="assistant", content="hi"),
    ]
    out = repair_tool_pairing(history)
    assert all(not (m.role == "tool" and m.tool_call_id == "ghost") for m in out)
    assert [m.role for m in out] == ["user", "assistant"]


def test_partial_answer_only_missing_gets_placeholder() -> None:
    history = [
        _asst(("c1", "a"), ("c2", "b")),  # two parallel calls
        _tool("c1"),  # only c1 answered
    ]
    out = repair_tool_pairing(history)
    result_ids = [m.tool_call_id for m in out if m.role == "tool"]
    assert set(result_ids) == {"c1", "c2"}
    placeholders = [m for m in out if m.role == "tool" and m.content == _PLACEHOLDER]
    assert len(placeholders) == 1 and placeholders[0].tool_call_id == "c2"


def test_idempotent() -> None:
    history = [_asst(("c1", "a"))]
    once = repair_tool_pairing(history)
    twice = repair_tool_pairing(once)
    assert [(m.role, m.tool_call_id, m.content) for m in once] == [
        (m.role, m.tool_call_id, m.content) for m in twice
    ]


def test_fenced_assistant_without_native_calls_unchanged() -> None:
    # Fenced mode keeps calls in the text, tool_calls=[] → nothing to pair.
    history = [Message(role="assistant", content="```veles-tool\nsearch\n```", tool_calls=[])]
    assert repair_tool_pairing(history) is history


# --- integration: the agent loop applies the repair before the provider call ---


def test_agent_repairs_orphan_before_provider_call() -> None:
    """A compressor that strips tool results (mimicking a split from
    compression / truncation) would leave turn 2 with an orphaned tool_call;
    the strict provider raises on that — exactly like the real HTTP 400. The
    repair must re-pair it so the turn completes."""
    from veles.core.agent import Agent
    from veles.core.provider import ProviderResponse, TokenUsage
    from veles.core.tools.registry import registry

    class _StrictProvider:
        name = "stub"
        supports_tools = True
        supports_streaming = False

        def __init__(self) -> None:
            self.n = 0

        def create_message(self, messages, tools=None, *, model, max_tokens=4096):
            del tools, model, max_tokens
            call_ids = {tc.id for m in messages for tc in m.tool_calls}
            result_ids = {m.tool_call_id for m in messages if m.role == "tool"}
            missing = call_ids - result_ids
            assert not missing, f"orphaned tool_call reached the provider: {missing}"
            self.n += 1
            if self.n == 1:
                return ProviderResponse(
                    text=None,
                    tool_calls=[ToolCall(id="c1", name="does_not_exist", arguments={})],
                    usage=TokenUsage(total_tokens=1),
                    finish_reason="tool_use",
                )
            return ProviderResponse(
                text="done", tool_calls=[], usage=TokenUsage(total_tokens=1), finish_reason="stop"
            )

    def _strip_tool_results(history, session_id):
        del session_id
        return [m for m in history if m.role != "tool"]

    agent = Agent(_StrictProvider(), registry.subset([]), model="m", compressor=_strip_tool_results)
    result = agent.run("go")
    assert result.stopped_reason == "completed"
    assert result.text == "done"
