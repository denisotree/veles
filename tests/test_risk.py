"""Tests for core/risk.py — Tier ε M65 taxonomy."""

from __future__ import annotations

from veles.core.risk import (
    DEFAULT_POLICY,
    RiskClass,
    is_sensitive_class,
)


def test_every_risk_class_has_a_default_policy() -> None:
    """Taxonomy invariant: adding a new class must come with a default decision."""
    for rc in RiskClass:
        assert rc in DEFAULT_POLICY


def test_default_policies_are_valid_decision_keys() -> None:
    valid = {"allow", "approval_required", "always_confirm"}
    for rc, decision in DEFAULT_POLICY.items():
        assert decision in valid, f"{rc} -> {decision}"


def test_read_side_defaults_to_allow() -> None:
    for rc in (
        RiskClass.READ_ONLY,
        RiskClass.SEARCH_ONLY,
        RiskClass.COMPUTE_ONLY,
        RiskClass.DRAFT_ONLY,
    ):
        assert DEFAULT_POLICY[rc] == "allow"


def test_external_and_execution_default_to_approval() -> None:
    for rc in (
        RiskClass.WRITE_EXTERNAL,
        RiskClass.NETWORK_OPEN_WORLD,
        RiskClass.PROCESS_EXECUTION,
    ):
        assert DEFAULT_POLICY[rc] == "approval_required"


def test_destructive_and_admin_are_always_confirm() -> None:
    assert DEFAULT_POLICY[RiskClass.DESTRUCTIVE] == "always_confirm"
    assert DEFAULT_POLICY[RiskClass.PRIVILEGED_ADMIN] == "always_confirm"


def test_is_sensitive_class_matches_legacy_gate() -> None:
    """Bridge to existing `entry.sensitive`: write_external / network /
    process_execution / destructive / privileged_admin must all flip
    `sensitive=True`. Read-side never does."""
    sensitive = {rc for rc in RiskClass if is_sensitive_class(rc)}
    expected = {
        RiskClass.WRITE_EXTERNAL,
        RiskClass.NETWORK_OPEN_WORLD,
        RiskClass.PROCESS_EXECUTION,
        RiskClass.DESTRUCTIVE,
        RiskClass.PRIVILEGED_ADMIN,
    }
    assert sensitive == expected
