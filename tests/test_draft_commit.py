"""Tests for the M72 draft/commit pairing convention.

Pairing is enforced by `_draft_commit_rule` in the Permission Engine:
the commit half is denied until the draft half appears in the per-session
invocation set.
"""

from __future__ import annotations

from tests.conftest import StubProvider as _StubProvider
from veles.core.agent import Agent
from veles.core.agent_state import (
    clear_invoked_tools,
    invoked_tools,
    record_invocation,
    reset_invoked_tools,
)
from veles.core.permission import evaluate as evaluate_permission
from veles.core.provider import ProviderResponse, TokenUsage, ToolCall
from veles.core.risk import RiskClass
from veles.core.tools.registry import Registry, ToolEntry

# ---------- engine rule, unit-level ----------


def _commit_entry() -> ToolEntry:
    return ToolEntry(
        name="send_email",
        description="send the drafted email",
        parameter_schema={"type": "object"},
        handler=lambda: "sent",
        is_async=False,
        sensitive=True,
        risk_class=RiskClass.WRITE_EXTERNAL,
        commit_of="draft_email",
    )


def test_commit_denied_without_draft() -> None:
    tok = clear_invoked_tools()
    try:
        d = evaluate_permission(_commit_entry(), {})
    finally:
        reset_invoked_tools(tok)
    assert d.kind == "deny"
    assert d.rule == "draft_commit"
    assert "draft_email" in d.reason


def test_commit_allowed_after_draft_recorded() -> None:
    tok = clear_invoked_tools()
    try:
        record_invocation("draft_email")
        d = evaluate_permission(_commit_entry(), {})
    finally:
        reset_invoked_tools(tok)
    # Past the draft_commit gate; next rule fires. Since this is
    # WRITE_EXTERNAL + sensitive=True, the trust_ladder takes over.
    # Either way, it's NOT a draft_commit deny.
    assert d.rule != "draft_commit"


def test_non_commit_tool_not_affected() -> None:
    """Tools without `commit_of` skip the draft_commit rule entirely."""
    entry = ToolEntry(
        name="read_file",
        description="d",
        parameter_schema={"type": "object"},
        handler=lambda: "x",
        is_async=False,
        risk_class=RiskClass.READ_ONLY,
    )
    tok = clear_invoked_tools()
    try:
        d = evaluate_permission(entry, {})
    finally:
        reset_invoked_tools(tok)
    assert d.rule != "draft_commit"
    assert d.kind == "allow"


def test_draft_commit_fires_before_trust_ladder() -> None:
    """Even if the user would grant the commit tool via trust_ladder, the
    draft_commit rule short-circuits first when the draft hasn't run."""
    tok = clear_invoked_tools()
    try:
        d = evaluate_permission(_commit_entry(), {})
    finally:
        reset_invoked_tools(tok)
    assert d.rule == "draft_commit"


# ---------- ContextVar tracking ----------


def test_record_invocation_accumulates() -> None:
    tok = clear_invoked_tools()
    try:
        assert invoked_tools() == frozenset()
        record_invocation("a")
        record_invocation("b")
        record_invocation("a")
        assert invoked_tools() == frozenset({"a", "b"})
    finally:
        reset_invoked_tools(tok)


def test_invocation_set_isolated_after_reset() -> None:
    """`clear_invoked_tools` plus its reset token correctly tear down the
    ContextVar — what you record between them never leaks to the next test."""
    tok = clear_invoked_tools()
    record_invocation("x")
    reset_invoked_tools(tok)
    assert "x" not in invoked_tools()


# ---------- Agent end-to-end ----------


def _pair_registry(draft_handler, commit_handler) -> Registry:
    reg = Registry()
    reg.register(
        ToolEntry(
            name="draft_email",
            description="draft",
            parameter_schema={"type": "object"},
            handler=draft_handler,
            is_async=False,
            risk_class=RiskClass.DRAFT_ONLY,
        )
    )
    reg.register(
        ToolEntry(
            name="send_email",
            description="commit",
            parameter_schema={"type": "object"},
            handler=commit_handler,
            is_async=False,
            sensitive=True,
            risk_class=RiskClass.WRITE_EXTERNAL,
            commit_of="draft_email",
        )
    )
    return reg


def test_agent_denies_commit_before_draft() -> None:
    """Full Agent loop: model jumps straight to send_email without drafting.
    Engine denies, handler never runs."""
    commit_called = {"n": 0}

    def commit_handler() -> str:
        commit_called["n"] += 1
        return "sent"

    provider = _StubProvider(
        responses=[
            ProviderResponse(
                text=None,
                tool_calls=[ToolCall(id="c1", name="send_email", arguments={})],
                usage=TokenUsage(total_tokens=1),
                finish_reason="tool_use",
            ),
            ProviderResponse(
                text="oh I should draft first",
                tool_calls=[],
                usage=TokenUsage(total_tokens=1),
                finish_reason="stop",
            ),
        ]
    )
    agent = Agent(provider, _pair_registry(lambda: "drafted", commit_handler), model="m")
    result = agent.run("send the email")
    tool_msg = next(m for m in result.history if m.role == "tool")
    assert tool_msg.content is not None
    assert "refused by draft_commit" in tool_msg.content
    assert commit_called["n"] == 0


def test_agent_allows_commit_after_draft_within_same_run() -> None:
    """Model emits draft_email then send_email in the same run; the
    invocation set carries draft_email into the second call's evaluation."""
    from veles.core.permission.prompt import (
        PromptAnswer,
    )
    from veles.core.permission.prompt import (
        reset_prompter as reset_unified_prompter,
    )
    from veles.core.permission.prompt import (
        set_prompter as set_unified_prompter,
    )
    from veles.core.trust import begin_trust_turn, end_trust_turn

    commit_called = {"n": 0}

    def commit_handler() -> str:
        commit_called["n"] += 1
        return "sent"

    provider = _StubProvider(
        responses=[
            # Model invokes draft first.
            ProviderResponse(
                text=None,
                tool_calls=[ToolCall(id="d1", name="draft_email", arguments={})],
                usage=TokenUsage(total_tokens=1),
                finish_reason="tool_use",
            ),
            # Then asks for commit.
            ProviderResponse(
                text=None,
                tool_calls=[ToolCall(id="c1", name="send_email", arguments={})],
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
    # Pre-approve the commit via trust ladder so the dispatch can proceed
    # past the trust_ladder rule (which fires *after* draft_commit).
    token = begin_trust_turn()
    pt = set_unified_prompter(lambda _req: PromptAnswer("allow_once"))
    try:
        agent = Agent(provider, _pair_registry(lambda: "drafted", commit_handler), model="m")
        agent.run("send the email")
    finally:
        reset_unified_prompter(pt)
        end_trust_turn(token)
    assert commit_called["n"] == 1
