"""Integration: Agent dispatch fires record_approval on user-facing rules (M73)."""

from __future__ import annotations

from pathlib import Path

from tests.conftest import StubProvider as _StubProvider
from veles.core.agent import Agent
from veles.core.approval import APPROVALS_DIRNAME, list_approvals
from veles.core.critical_ops import reset_critical_confirmer, set_critical_confirmer
from veles.core.permission.prompt import (
    PromptAnswer,
    reset_prompter as reset_unified_prompter,
    set_prompter as set_unified_prompter,
)
from veles.core.provider import ProviderResponse, TokenUsage, ToolCall
from veles.core.risk import RiskClass
from veles.core.tools.registry import Registry, ToolEntry
from veles.core.trust import begin_trust_turn, end_trust_turn


def _final(text: str = "done") -> ProviderResponse:
    return ProviderResponse(
        text=text,
        tool_calls=[],
        usage=TokenUsage(total_tokens=1),
        finish_reason="stop",
    )


def _tool_call(name: str, args: dict) -> ProviderResponse:
    return ProviderResponse(
        text=None,
        tool_calls=[ToolCall(id="c1", name=name, arguments=args)],
        usage=TokenUsage(total_tokens=1),
        finish_reason="tool_use",
    )


def _sensitive_tool(name: str, rc: RiskClass = RiskClass.PROCESS_EXECUTION) -> Registry:
    reg = Registry()
    reg.register(
        ToolEntry(
            name=name,
            description="d",
            parameter_schema={"type": "object"},
            handler=lambda: "ok",
            is_async=False,
            sensitive=True,
            risk_class=rc,
        )
    )
    return reg


def _destructive_tool(name: str) -> Registry:
    return _sensitive_tool(name, rc=RiskClass.DESTRUCTIVE)


def _import_dispatch():
    # Import lazily so we can patch through agent module.
    from veles.core import agent as agent_mod

    return agent_mod._dispatch


# ---------- positive cases ----------


def test_approval_written_when_trust_ladder_allows(tmp_path: Path) -> None:
    """User-facing trust-ladder allow → one approval record on disk."""
    state_dir = tmp_path
    reg = _sensitive_tool("danger")
    provider = _StubProvider(responses=[_tool_call("danger", {"x": 1}), _final("ok")])

    token = begin_trust_turn()
    pt = set_unified_prompter(lambda _req: PromptAnswer("allow_once"))
    try:
        # Pass approval_dir through agent loop by mocking active project.
        from veles.core import context as ctx_mod
        from veles.core.project import Project

        proj = Project(root=state_dir, name="t", created_at=0.0)
        # Ensure state_dir exists for the bare project.
        (state_dir / ".veles").mkdir(parents=True, exist_ok=True)
        ptoken = ctx_mod.set_active_project(proj)
        try:
            agent = Agent(provider, reg, model="m")
            agent.run("danger run")
        finally:
            ctx_mod.reset_active_project(ptoken)
    finally:
        reset_unified_prompter(pt)
        end_trust_turn(token)

    approvals = list_approvals(proj.state_dir)
    assert len(approvals) == 1
    rec = approvals[0]
    assert rec["tool_name"] == "danger"
    assert rec["rule"] == "trust_ladder"
    assert rec["approver"] == "user"
    assert rec["arguments"] == {"x": 1}


def test_approval_written_for_always_confirm_allow(tmp_path: Path) -> None:
    """Critical-confirm allow → record with rule=always_confirm."""
    state_dir = tmp_path
    reg = _destructive_tool("nuke")
    provider = _StubProvider(responses=[_tool_call("nuke", {}), _final("ok")])

    ct = set_critical_confirmer(lambda _op, _summary: True)
    try:
        from veles.core import context as ctx_mod
        from veles.core.project import Project

        proj = Project(root=state_dir, name="t", created_at=0.0)
        (state_dir / ".veles").mkdir(parents=True, exist_ok=True)
        ptoken = ctx_mod.set_active_project(proj)
        try:
            agent = Agent(provider, reg, model="m")
            agent.run("trigger")
        finally:
            ctx_mod.reset_active_project(ptoken)
    finally:
        reset_critical_confirmer(ct)

    approvals = list_approvals(proj.state_dir)
    assert len(approvals) == 1
    assert approvals[0]["rule"] == "always_confirm"


def test_approval_marks_autopilot_when_via_autopilot(tmp_path: Path) -> None:
    """When the trust ladder allows via autopilot, the record's approver
    is 'autopilot', not 'user'."""
    import time

    from veles.core.autopilot import activate as activate_autopilot
    from veles.core.autopilot import deactivate as deactivate_autopilot

    state_dir = tmp_path
    reg = _sensitive_tool("danger")
    provider = _StubProvider(responses=[_tool_call("danger", {}), _final("ok")])

    activate_autopilot(time.time() + 3600)
    try:
        from veles.core import context as ctx_mod
        from veles.core.project import Project

        proj = Project(root=state_dir, name="t", created_at=0.0)
        (state_dir / ".veles").mkdir(parents=True, exist_ok=True)
        ptoken = ctx_mod.set_active_project(proj)
        try:
            agent = Agent(provider, reg, model="m")
            agent.run("autopilot try")
        finally:
            ctx_mod.reset_active_project(ptoken)
    finally:
        deactivate_autopilot()

    approvals = list_approvals(proj.state_dir)
    assert len(approvals) == 1
    assert approvals[0]["approver"] == "autopilot"
    assert approvals[0]["via_autopilot"] is True


# ---------- negative cases (no record written) ----------


def test_no_approval_for_read_only_tool(tmp_path: Path) -> None:
    """Non-sensitive tools never trigger an approval — that's noise, not
    audit signal."""
    state_dir = tmp_path
    reg = Registry()
    reg.register(
        ToolEntry(
            name="reader",
            description="d",
            parameter_schema={"type": "object"},
            handler=lambda: "out",
            is_async=False,
            risk_class=RiskClass.READ_ONLY,
        )
    )
    provider = _StubProvider(responses=[_tool_call("reader", {}), _final("ok")])

    from veles.core import context as ctx_mod
    from veles.core.project import Project

    proj = Project(root=state_dir, name="t", created_at=0.0)
    (state_dir / ".veles").mkdir(parents=True, exist_ok=True)
    ptoken = ctx_mod.set_active_project(proj)
    try:
        agent = Agent(provider, reg, model="m")
        agent.run("read")
    finally:
        ctx_mod.reset_active_project(ptoken)

    assert list_approvals(proj.state_dir) == []
    # The approvals dir is created only when at least one record is written.
    assert not (proj.state_dir / APPROVALS_DIRNAME).exists()


def test_no_approval_on_denial(tmp_path: Path) -> None:
    """A REFUSE through the trust ladder must NOT record an approval —
    we only log grants, not refusals (refusals already land in events.jsonl
    via PermissionDecision)."""
    state_dir = tmp_path
    reg = _sensitive_tool("danger")
    provider = _StubProvider(responses=[_tool_call("danger", {}), _final("ok")])

    token = begin_trust_turn()
    pt = set_unified_prompter(lambda _req: PromptAnswer("deny"))
    try:
        from veles.core import context as ctx_mod
        from veles.core.project import Project

        proj = Project(root=state_dir, name="t", created_at=0.0)
        (state_dir / ".veles").mkdir(parents=True, exist_ok=True)
        ptoken = ctx_mod.set_active_project(proj)
        try:
            agent = Agent(provider, reg, model="m")
            agent.run("danger")
        finally:
            ctx_mod.reset_active_project(ptoken)
    finally:
        reset_unified_prompter(pt)
        end_trust_turn(token)

    assert list_approvals(proj.state_dir) == []


def test_no_approval_when_no_active_project(tmp_path: Path) -> None:
    """Without an active project there's no state_dir — the hook silently
    no-ops (it cannot decide where to write). The run still completes."""
    reg = _sensitive_tool("danger")
    provider = _StubProvider(responses=[_tool_call("danger", {}), _final("ok")])

    token = begin_trust_turn()
    pt = set_unified_prompter(lambda _req: PromptAnswer("allow_once"))
    try:
        agent = Agent(provider, reg, model="m")
        agent.run("danger")
    finally:
        reset_unified_prompter(pt)
        end_trust_turn(token)

    # tmp_path should be untouched — no approvals dir anywhere.
    assert list(tmp_path.iterdir()) == []
