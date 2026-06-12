"""Tests for Planning mode runtime state — Tier ε M71.

Covers three layers:
  1. AgentState enum + ContextVar accessors.
  2. Permission Engine `planning_mode` rule: mutation tools denied while
     state is PLANNING.
  3. Agent end-to-end: `plan_mode=True` causes mutation tools to be
     rejected with a structured tool message instead of dispatching.
"""

from __future__ import annotations

from tests.conftest import StubProvider as _StubProvider
from veles.core.agent import Agent
from veles.core.agent_state import AgentState, current_state, is_planning, reset_state, set_state
from veles.core.permission import evaluate as evaluate_permission
from veles.core.provider import ProviderResponse, TokenUsage, ToolCall
from veles.core.risk import RiskClass, is_mutation_class
from veles.core.tools.registry import Registry, ToolEntry

# ---------- AgentState basics ----------


def test_default_state_is_idle() -> None:
    assert current_state() is AgentState.IDLE
    assert is_planning() is False


def test_set_state_planning_flips_predicate() -> None:
    tok = set_state(AgentState.PLANNING)
    try:
        assert current_state() is AgentState.PLANNING
        assert is_planning() is True
    finally:
        reset_state(tok)
    assert is_planning() is False


def test_reset_state_restores_previous_value() -> None:
    tok1 = set_state(AgentState.PLANNING)
    tok2 = set_state(AgentState.CALLING)
    assert current_state() is AgentState.CALLING
    reset_state(tok2)
    assert current_state() is AgentState.PLANNING
    reset_state(tok1)
    assert current_state() is AgentState.IDLE


# ---------- mutation taxonomy ----------


def test_mutation_classes_are_disjoint_from_read_side() -> None:
    """Read-side tools must NEVER be denied by Planning mode."""
    for rc in (
        RiskClass.READ_ONLY,
        RiskClass.SEARCH_ONLY,
        RiskClass.COMPUTE_ONLY,
        RiskClass.DRAFT_ONLY,
    ):
        assert is_mutation_class(rc) is False


def test_write_and_execute_classes_are_mutations() -> None:
    for rc in (
        RiskClass.WRITE_LOCAL_PROJECT,
        RiskClass.WRITE_LOCAL_USER_GLOBAL,
        RiskClass.WRITE_EXTERNAL,
        RiskClass.NETWORK_OPEN_WORLD,
        RiskClass.PROCESS_EXECUTION,
        RiskClass.DESTRUCTIVE,
        RiskClass.PRIVILEGED_ADMIN,
    ):
        assert is_mutation_class(rc) is True


# ---------- Permission Engine rule ----------


def _entry(rc: RiskClass | None = None, *, sensitive: bool = False) -> ToolEntry:
    return ToolEntry(
        name=f"t-{rc.value if rc else 'none'}",
        description="d",
        parameter_schema={"type": "object"},
        handler=lambda: "ok",
        is_async=False,
        sensitive=sensitive,
        risk_class=rc,
    )


def test_planning_blocks_write_local_project() -> None:
    tok = set_state(AgentState.PLANNING)
    try:
        d = evaluate_permission(_entry(RiskClass.WRITE_LOCAL_PROJECT, sensitive=True), {})
    finally:
        reset_state(tok)
    assert d.kind == "deny"
    assert d.rule == "planning_mode"
    assert "planning mode" in d.reason


def test_planning_blocks_process_execution() -> None:
    tok = set_state(AgentState.PLANNING)
    try:
        d = evaluate_permission(_entry(RiskClass.PROCESS_EXECUTION, sensitive=True), {})
    finally:
        reset_state(tok)
    assert d.kind == "deny"
    assert d.rule == "planning_mode"


def test_planning_allows_read_only() -> None:
    tok = set_state(AgentState.PLANNING)
    try:
        d = evaluate_permission(_entry(RiskClass.READ_ONLY), {})
    finally:
        reset_state(tok)
    assert d.kind == "allow"
    assert d.rule == "risk_default"


def test_planning_allows_search_compute_draft() -> None:
    for rc in (RiskClass.SEARCH_ONLY, RiskClass.COMPUTE_ONLY, RiskClass.DRAFT_ONLY):
        tok = set_state(AgentState.PLANNING)
        try:
            d = evaluate_permission(_entry(rc), {})
        finally:
            reset_state(tok)
        assert d.kind == "allow", f"{rc} should be allowed in planning mode"


def test_idle_state_does_not_trigger_planning_rule() -> None:
    """When state is anything other than PLANNING, the rule is a no-op."""
    # State defaults to IDLE; mutation tools fall through to trust_ladder
    # or risk_default as usual.
    d = evaluate_permission(_entry(RiskClass.WRITE_LOCAL_PROJECT), {})
    assert d.rule != "planning_mode"


def test_planning_blocks_before_always_confirm() -> None:
    """Even a DESTRUCTIVE tool — which would normally route through the
    always_confirm prompt — must be denied earlier by planning_mode. This
    keeps Planning mode a pure read-side phase: no prompt at all, not
    even a confirm dialog."""
    tok = set_state(AgentState.PLANNING)
    try:
        d = evaluate_permission(_entry(RiskClass.DESTRUCTIVE, sensitive=True), {})
    finally:
        reset_state(tok)
    assert d.rule == "planning_mode"
    assert d.kind == "deny"


# ---------- Agent end-to-end ----------


def _writer_registry() -> Registry:
    reg = Registry()
    reg.register(
        ToolEntry(
            name="write_thing",
            description="writes",
            parameter_schema={"type": "object"},
            handler=lambda: "wrote",
            is_async=False,
            sensitive=True,
            risk_class=RiskClass.WRITE_LOCAL_PROJECT,
        )
    )
    return reg


def test_agent_plan_mode_refuses_writers() -> None:
    """The full agent loop with plan_mode=True must reject a write tool
    call without dispatching the handler."""
    provider = _StubProvider(
        responses=[
            ProviderResponse(
                text=None,
                tool_calls=[ToolCall(id="c1", name="write_thing", arguments={})],
                usage=TokenUsage(total_tokens=1),
                finish_reason="tool_use",
            ),
            ProviderResponse(
                text="acknowledged refusal",
                tool_calls=[],
                usage=TokenUsage(total_tokens=1),
                finish_reason="stop",
            ),
        ]
    )
    handler_called = {"count": 0}

    def _spy_handler() -> str:
        handler_called["count"] += 1
        return "wrote"

    reg = Registry()
    reg.register(
        ToolEntry(
            name="write_thing",
            description="writes",
            parameter_schema={"type": "object"},
            handler=_spy_handler,
            is_async=False,
            sensitive=True,
            risk_class=RiskClass.WRITE_LOCAL_PROJECT,
        )
    )
    agent = Agent(provider, reg, model="m", plan_mode=True)
    result = agent.run("plan it")
    tool_msg = next(m for m in result.history if m.role == "tool")
    assert tool_msg.content is not None
    assert "refused by planning_mode" in tool_msg.content
    # Critically: the handler never ran.
    assert handler_called["count"] == 0


def test_agent_plan_mode_resets_state_after_run() -> None:
    """Planning state lives only for the duration of one run() call."""
    provider = _StubProvider(
        responses=[
            ProviderResponse(
                text="done",
                tool_calls=[],
                usage=TokenUsage(total_tokens=1),
                finish_reason="stop",
            )
        ]
    )
    assert current_state() is AgentState.IDLE
    agent = Agent(provider, Registry(), model="m", plan_mode=True)
    agent.run("hi")
    assert current_state() is AgentState.IDLE  # restored


def test_agent_default_no_plan_mode() -> None:
    """Backward compat: existing call sites that don't pass plan_mode
    keep observing IDLE state during run."""
    provider = _StubProvider(
        responses=[
            ProviderResponse(
                text="done",
                tool_calls=[],
                usage=TokenUsage(total_tokens=1),
                finish_reason="stop",
            )
        ]
    )
    agent = Agent(provider, _writer_registry(), model="m")
    # Doesn't trip the planning rule; the absence of `plan_mode=True`
    # means state is IDLE during run.
    result = agent.run("hi")
    assert result.text == "done"
