"""Tests for core/risk.py — Tier ε M65 taxonomy."""

from __future__ import annotations

from veles.core.risk import (
    DEFAULT_POLICY,
    RiskClass,
    auto_retry_allowed,
    default_decision,
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
        assert default_decision(rc) == "allow"


def test_external_and_execution_default_to_approval() -> None:
    for rc in (
        RiskClass.WRITE_EXTERNAL,
        RiskClass.NETWORK_OPEN_WORLD,
        RiskClass.PROCESS_EXECUTION,
    ):
        assert default_decision(rc) == "approval_required"


def test_destructive_and_admin_are_always_confirm() -> None:
    assert default_decision(RiskClass.DESTRUCTIVE) == "always_confirm"
    assert default_decision(RiskClass.PRIVILEGED_ADMIN) == "always_confirm"


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


def test_auto_retry_only_for_safe_classes() -> None:
    safe = {
        RiskClass.READ_ONLY,
        RiskClass.SEARCH_ONLY,
        RiskClass.COMPUTE_ONLY,
        RiskClass.DRAFT_ONLY,
    }
    for rc in RiskClass:
        assert auto_retry_allowed(rc) == (rc in safe)
