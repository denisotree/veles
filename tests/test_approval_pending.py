"""Tests for the M71 follow-up: interactive `approval_required` wiring."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import StubProvider as _StubProvider
from veles.core.agent import Agent
from veles.core.agent_state import AgentState, current_state
from veles.core.approval_prompter import ApprovalAnswer, ask_for_approval
from veles.core.permission import Decision, evaluate
from veles.core.permission.prompt import (
    PromptAnswer,
    PromptRequest,
    current_prompter,
    reset_prompter,
    set_prompter,
)
from veles.core.provider import ProviderResponse, TokenUsage, ToolCall
from veles.core.risk import RiskClass
from veles.core.tools.registry import Registry, ToolEntry


# ---------- prompter ContextVar ----------


def test_default_prompter_denies_when_non_interactive() -> None:
    """The default prompter refuses non-TTY contexts so headless runs
    never deadlock on input that will never arrive."""
    # pytest captures stdin; isatty returns False there.
    answer = ask_for_approval("danger", {"x": 1}, "needs approval")
    assert isinstance(answer, ApprovalAnswer)
    assert answer.approved is False


def test_custom_prompter_can_approve() -> None:
    seen: dict[str, object] = {}

    def _ok(req: PromptRequest) -> PromptAnswer:
        seen["name"] = req.tool_name
        seen["args"] = req.arguments
        seen["reason"] = req.reason
        return PromptAnswer("allow_once")

    token = set_prompter(_ok)
    try:
        answer = ask_for_approval("ship_email", {"to": "x"}, "needs approval")
    finally:
        reset_prompter(token)
    assert answer.approved is True
    assert seen["name"] == "ship_email"
    assert seen["args"] == {"to": "x"}


def test_prompter_exception_degrades_to_deny() -> None:
    """Bug in a user-supplied prompter must not block the loop."""

    def _bad(_req: PromptRequest) -> PromptAnswer:
        raise RuntimeError("oops")

    token = set_prompter(_bad)
    try:
        answer = ask_for_approval("x", {}, "")
    finally:
        reset_prompter(token)
    assert answer.approved is False


def test_set_and_reset_prompter_isolates_state() -> None:
    saved = current_prompter()

    def _yes(_req: PromptRequest) -> PromptAnswer:
        return PromptAnswer("allow_once")

    token = set_prompter(_yes)
    assert current_prompter() is _yes
    reset_prompter(token)
    assert current_prompter() is saved


# ---------- engine output that triggers the wiring ----------


def _entry_no_sensitive(rc: RiskClass) -> ToolEntry:
    """Tool with a high risk class but `sensitive=False` — explicit override
    that keeps the trust ladder out of the picture so risk_default fires."""
    return ToolEntry(
        name=f"r-{rc.value}",
        description="d",
        parameter_schema={"type": "object"},
        handler=lambda: "ok",
        is_async=False,
        sensitive=False,
        risk_class=rc,
    )


def test_engine_returns_approval_required_for_non_sensitive_external() -> None:
    """When a write_external / network_open_world / process_execution tool
    is configured with sensitive=False (an explicit override; the default
    decorator path auto-flags it sensitive), the engine routes it to
    risk_default which yields approval_required — the exact path this
    follow-up wires into an interactive prompt."""
    d = evaluate(_entry_no_sensitive(RiskClass.WRITE_EXTERNAL), {})
    assert d.kind == "approval_required"
    assert d.rule == "risk_default"


# ---------- Agent end-to-end ----------


def _registry_with_approval_tool(handler) -> Registry:  # noqa: ANN001
    reg = Registry()
    reg.register(
        ToolEntry(
            name="post_thing",
            description="external write",
            parameter_schema={"type": "object"},
            handler=handler,
            is_async=False,
            sensitive=False,  # forces engine to risk_default → approval_required
            risk_class=RiskClass.WRITE_EXTERNAL,
        )
    )
    return reg


def test_agent_consults_prompter_on_approval_required() -> None:
    """End-to-end: model invokes a tool that yields approval_required;
    the agent calls the prompter; when prompter returns True, the
    handler actually runs."""
    handler_calls = {"n": 0, "data": None}

    def handler(**kwargs: object) -> str:
        handler_calls["n"] += 1
        handler_calls["data"] = kwargs.get("data")
        return "posted"

    provider = _StubProvider(
        responses=[
            ProviderResponse(
                text=None,
                tool_calls=[ToolCall(id="c1", name="post_thing", arguments={"data": 1})],
                usage=TokenUsage(total_tokens=1),
                finish_reason="tool_use",
            ),
            ProviderResponse(
                text="done",
                tool_calls=[],
                usage=TokenUsage(total_tokens=1),
                finish_reason="stop",
            ),
        ]
    )

    seen: dict[str, object] = {}

    def _approver(req: PromptRequest) -> PromptAnswer:
        seen["name"] = req.tool_name
        seen["args"] = req.arguments
        seen["reason"] = req.reason
        return PromptAnswer("allow_once")

    token = set_prompter(_approver)
    try:
        agent = Agent(provider, _registry_with_approval_tool(handler), model="m")
        agent.run("post it")
    finally:
        reset_prompter(token)

    # Handler actually ran, with the args the model emitted.
    assert handler_calls["n"] == 1
    assert handler_calls["data"] == 1
    # Prompter received the right args.
    assert seen["name"] == "post_thing"
    assert seen["args"] == {"data": 1}


def test_agent_denial_via_prompter_blocks_dispatch() -> None:
    handler_calls = {"n": 0}

    def handler() -> str:
        handler_calls["n"] += 1
        return "posted"

    provider = _StubProvider(
        responses=[
            ProviderResponse(
                text=None,
                tool_calls=[ToolCall(id="c1", name="post_thing", arguments={})],
                usage=TokenUsage(total_tokens=1),
                finish_reason="tool_use",
            ),
            ProviderResponse(
                text="ok",
                tool_calls=[],
                usage=TokenUsage(total_tokens=1),
                finish_reason="stop",
            ),
        ]
    )
    token = set_prompter(lambda _req: PromptAnswer("deny"))
    try:
        agent = Agent(provider, _registry_with_approval_tool(handler), model="m")
        result = agent.run("post it")
    finally:
        reset_prompter(token)

    assert handler_calls["n"] == 0
    tool_msg = next(m for m in result.history if m.role == "tool")
    assert tool_msg.content is not None
    assert "refused by approval_prompt" in tool_msg.content


def test_agent_state_flips_during_prompter() -> None:
    """When the prompter runs, AgentState must be APPROVAL_PENDING. After
    the answer, state goes back to whatever the run set it to (IDLE)."""
    observed = {}

    def _capture(_req: PromptRequest) -> PromptAnswer:
        observed["state"] = current_state()
        return PromptAnswer("allow_once")

    provider = _StubProvider(
        responses=[
            ProviderResponse(
                text=None,
                tool_calls=[ToolCall(id="c1", name="post_thing", arguments={})],
                usage=TokenUsage(total_tokens=1),
                finish_reason="tool_use",
            ),
            ProviderResponse(
                text="ok",
                tool_calls=[],
                usage=TokenUsage(total_tokens=1),
                finish_reason="stop",
            ),
        ]
    )

    def handler() -> str:
        return "x"

    token = set_prompter(_capture)
    try:
        agent = Agent(provider, _registry_with_approval_tool(handler), model="m")
        agent.run("go")
    finally:
        reset_prompter(token)

    assert observed.get("state") is AgentState.APPROVAL_PENDING
    # After run completes, ContextVar is reset.
    assert current_state() is AgentState.IDLE


def test_approval_prompt_creates_audit_record(tmp_path: Path) -> None:
    """When the user approves via the interactive prompt, the audit log
    receives a fresh ApprovalRecord with rule='approval_prompt'."""
    from veles.core.approval import list_approvals
    from veles.core.context import reset_active_project, set_active_project
    from veles.core.project import Project

    state_dir = tmp_path / ".veles"
    state_dir.mkdir()
    proj = Project(root=tmp_path, name="t", created_at=0.0)

    provider = _StubProvider(
        responses=[
            ProviderResponse(
                text=None,
                tool_calls=[ToolCall(id="c1", name="post_thing", arguments={})],
                usage=TokenUsage(total_tokens=1),
                finish_reason="tool_use",
            ),
            ProviderResponse(
                text="done",
                tool_calls=[],
                usage=TokenUsage(total_tokens=1),
                finish_reason="stop",
            ),
        ]
    )
    p_token = set_prompter(lambda _req: PromptAnswer("allow_once"))
    proj_token = set_active_project(proj)
    try:
        agent = Agent(provider, _registry_with_approval_tool(lambda: "ok"), model="m")
        agent.run("go")
    finally:
        reset_active_project(proj_token)
        reset_prompter(p_token)

    records = list_approvals(proj.state_dir)
    assert len(records) == 1
    assert records[0]["rule"] == "approval_prompt"
    assert records[0]["tool_name"] == "post_thing"


def test_approval_events_emitted(tmp_path: Path) -> None:
    """ApprovalRequest + ApprovalResult land in events.jsonl for replay."""
    from veles.core.events import EventWriter, filter_events, read_events

    writer = EventWriter(tmp_path / "events.jsonl")
    provider = _StubProvider(
        responses=[
            ProviderResponse(
                text=None,
                tool_calls=[ToolCall(id="c1", name="post_thing", arguments={})],
                usage=TokenUsage(total_tokens=1),
                finish_reason="tool_use",
            ),
            ProviderResponse(
                text="ok",
                tool_calls=[],
                usage=TokenUsage(total_tokens=1),
                finish_reason="stop",
            ),
        ]
    )
    token = set_prompter(lambda _req: PromptAnswer("deny"))
    try:
        agent = Agent(
            provider,
            _registry_with_approval_tool(lambda: "x"),
            model="m",
            event_writer=writer,
        )
        agent.run("go")
    finally:
        reset_prompter(token)

    events = read_events(tmp_path / "events.jsonl")
    requests = filter_events(events, type_="approval_request")
    results = filter_events(events, type_="approval_result")
    assert len(requests) == 1
    assert requests[0]["target"] == "post_thing"
    assert len(results) == 1
    assert results[0]["status"] == "denied"
