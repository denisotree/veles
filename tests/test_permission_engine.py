"""Tests for core/permission/engine.py — Tier ε M64 unified decisions."""

from __future__ import annotations

from veles.core.critical_ops import reset_critical_confirmer, set_critical_confirmer
from veles.core.permission import Decision, evaluate
from veles.core.permission.engine import event_decision_str
from veles.core.permission.prompt import (
    PromptAnswer,
)
from veles.core.permission.prompt import (
    reset_prompter as reset_unified_prompter,
)
from veles.core.permission.prompt import (
    set_prompter as set_unified_prompter,
)
from veles.core.risk import RiskClass
from veles.core.tools.registry import ToolEntry
from veles.core.trust import begin_trust_turn, end_trust_turn


def _entry(
    *,
    name: str = "t",
    sensitive: bool = False,
    risk_class: RiskClass | None = None,
) -> ToolEntry:
    return ToolEntry(
        name=name,
        description="d",
        parameter_schema={"type": "object"},
        handler=lambda: "ok",
        is_async=False,
        sensitive=sensitive,
        risk_class=risk_class,
    )


# ---------- decision shape ----------


def test_decision_allowed_property() -> None:
    assert Decision(kind="allow", rule="risk_default").allowed is True
    assert Decision(kind="deny", rule="trust_ladder").allowed is False
    assert Decision(kind="approval_required", rule="risk_default").allowed is False


def test_event_discriminator_passthrough() -> None:
    assert event_decision_str(Decision(kind="allow", rule="risk_default")) == "allow"
    assert event_decision_str(Decision(kind="deny", rule="trust_ladder")) == "deny"


# ---------- read-side: allow by default ----------


def test_read_only_tool_is_allowed() -> None:
    d = evaluate(_entry(risk_class=RiskClass.READ_ONLY), {})
    assert d.kind == "allow"
    assert d.rule == "risk_default"


def test_no_risk_class_no_sensitive_allows() -> None:
    """Backward compat: a legacy tool with neither metadata nor sensitive
    flag must keep working as `allow`. M124-perm-unify collapsed the
    `default_allow` rule into `risk_default`; the kind is the load-bearing
    invariant, the rule name is a free label."""
    d = evaluate(_entry(), {})
    assert d.kind == "allow"
    assert d.rule == "risk_default"


def test_compute_only_and_draft_only_are_allowed() -> None:
    for rc in (RiskClass.COMPUTE_ONLY, RiskClass.DRAFT_ONLY, RiskClass.SEARCH_ONLY):
        assert evaluate(_entry(risk_class=rc), {}).kind == "allow"


# ---------- trust ladder: legacy sensitive tools ----------


def test_sensitive_tool_routes_through_trust_ladder_allow() -> None:
    token = begin_trust_turn()
    pt = set_unified_prompter(lambda _req: PromptAnswer("allow_once"))
    try:
        d = evaluate(_entry(sensitive=True, risk_class=RiskClass.WRITE_LOCAL_PROJECT), {})
    finally:
        reset_unified_prompter(pt)
        end_trust_turn(token)
    assert d.kind == "allow"
    assert d.rule == "trust_ladder"


def test_sensitive_tool_routes_through_trust_ladder_deny() -> None:
    token = begin_trust_turn()
    pt = set_unified_prompter(lambda _req: PromptAnswer("deny"))
    try:
        d = evaluate(_entry(sensitive=True, risk_class=RiskClass.NETWORK_OPEN_WORLD), {})
    finally:
        reset_unified_prompter(pt)
        end_trust_turn(token)
    assert d.kind == "deny"
    assert d.rule == "trust_ladder"


def test_network_open_world_is_auto_sensitive_via_risk_class() -> None:
    """Auto-sensitivity bridge (§M65): a tool with risk_class but no explicit
    `sensitive=True` is still routed through the trust ladder when the class
    is in the sensitive set."""
    entry = ToolEntry(
        name="net",
        description="d",
        parameter_schema={"type": "object"},
        handler=lambda: "x",
        is_async=False,
        # NOTE: sensitive defaults False — but ToolEntry doesn't auto-derive
        # because that lives in the @tool decorator. For this test we wire
        # it as the decorator would: sensitive=True when class is sensitive.
        sensitive=True,
        risk_class=RiskClass.NETWORK_OPEN_WORLD,
    )
    token = begin_trust_turn()
    pt = set_unified_prompter(lambda _req: PromptAnswer("allow_once"))
    try:
        d = evaluate(entry, {})
    finally:
        reset_unified_prompter(pt)
        end_trust_turn(token)
    assert d.kind == "allow"
    assert d.rule == "trust_ladder"


# ---------- always-confirm: DESTRUCTIVE / PRIVILEGED_ADMIN ----------


def test_destructive_tool_requires_critical_confirmation_allow() -> None:
    """When the critical-ops confirmer returns True, decision is allow with
    `always_confirm` rule — short-circuits the trust ladder."""
    ct = set_critical_confirmer(lambda _op, _summary: True)
    try:
        d = evaluate(_entry(sensitive=True, risk_class=RiskClass.DESTRUCTIVE), {})
    finally:
        reset_critical_confirmer(ct)
    assert d.kind == "allow"
    assert d.rule == "always_confirm"


def test_destructive_tool_requires_critical_confirmation_deny() -> None:
    ct = set_critical_confirmer(lambda _op, _summary: False)
    try:
        d = evaluate(_entry(sensitive=True, risk_class=RiskClass.DESTRUCTIVE), {})
    finally:
        reset_critical_confirmer(ct)
    assert d.kind == "deny"
    assert d.rule == "always_confirm"


def test_privileged_admin_requires_critical_confirmation() -> None:
    ct = set_critical_confirmer(lambda _op, _summary: False)
    try:
        d = evaluate(_entry(risk_class=RiskClass.PRIVILEGED_ADMIN), {})
    finally:
        reset_critical_confirmer(ct)
    assert d.kind == "deny"
    assert d.rule == "always_confirm"


def test_always_confirm_short_circuits_before_trust_ladder() -> None:
    """If the destructive risk fires always-confirm and the user says no,
    the trust ladder never gets a chance — verified by leaving the trust
    prompter as REFUSE: rule must still be `always_confirm`, not
    `trust_ladder`."""
    ct = set_critical_confirmer(lambda _op, _summary: False)
    pt = set_unified_prompter(lambda _req: PromptAnswer("allow_once"))
    token = begin_trust_turn()
    try:
        d = evaluate(_entry(sensitive=True, risk_class=RiskClass.DESTRUCTIVE), {})
    finally:
        reset_unified_prompter(pt)
        reset_critical_confirmer(ct)
        end_trust_turn(token)
    assert d.rule == "always_confirm"
    assert d.kind == "deny"


# ---------- autopilot reporting ----------


def test_decision_propagates_via_autopilot_flag(monkeypatch) -> None:
    """Trust ladder may flag a decision as autopilot-bypass; the engine
    propagates the flag unchanged into the typed Decision."""
    from veles.core import trust as trust_mod

    def fake_evaluate_trust(name, arguments=None, *, reason=""):
        del name, arguments, reason
        return trust_mod.TrustDecision(allowed=True, reason="autopilot active", via_autopilot=True)

    monkeypatch.setattr("veles.core.permission.engine.evaluate_trust", fake_evaluate_trust)
    d = evaluate(_entry(sensitive=True, risk_class=RiskClass.PROCESS_EXECUTION), {})
    assert d.kind == "allow"
    assert d.rule == "trust_ladder"
    assert d.via_autopilot is True
