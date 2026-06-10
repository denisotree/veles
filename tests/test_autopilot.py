"""M63 — autopilot state CRUD + duration parsing + trust-evaluator bypass."""

from __future__ import annotations

import datetime as _dt
import json
import time

import pytest

from veles.core.autopilot import (
    activate,
    autopilot_path,
    deactivate,
    format_remaining,
    is_active,
    load_state,
    parse_until,
)
from veles.core.trust import TrustDecision, evaluate_trust


# User-home isolation comes from the autouse `_hermetic_user_home`
# fixture in tests/conftest.py; only the trust bypass needs clearing here.
@pytest.fixture(autouse=True)
def _no_trust_auto_allow(monkeypatch):
    monkeypatch.delenv("VELES_TRUST_AUTO_ALLOW", raising=False)


# ---- state CRUD ----


def test_load_state_when_file_missing() -> None:
    state = load_state()
    assert state.active is False
    assert state.enabled_until == 0.0


def test_activate_writes_file_with_timestamp() -> None:
    until = time.time() + 3600
    activate(until)
    state = load_state()
    assert state.active is True
    assert pytest.approx(state.enabled_until, abs=1.0) == until
    assert state.seconds_remaining > 0


def test_deactivate_removes_file() -> None:
    activate(time.time() + 3600)
    assert autopilot_path().is_file()
    assert deactivate() is True
    assert not autopilot_path().is_file()
    assert deactivate() is False


def test_is_active_when_expired_returns_false() -> None:
    activate(time.time() - 60)
    assert is_active() is False
    # File stays for status reporting; expired but not auto-deleted.
    assert autopilot_path().is_file()


def test_load_state_permissive_on_corrupt_json() -> None:
    autopilot_path().parent.mkdir(parents=True, exist_ok=True)
    autopilot_path().write_text("not json", encoding="utf-8")
    state = load_state()
    assert state.active is False


def test_load_state_permissive_on_wrong_shape() -> None:
    autopilot_path().parent.mkdir(parents=True, exist_ok=True)
    autopilot_path().write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
    assert load_state().active is False


# ---- parse_until ----


def test_parse_until_seconds() -> None:
    target = parse_until("+30s")
    assert pytest.approx(target - time.time(), abs=1.0) == 30


def test_parse_until_minutes() -> None:
    target = parse_until("+15m")
    assert pytest.approx(target - time.time(), abs=1.0) == 15 * 60


def test_parse_until_hours() -> None:
    target = parse_until("+2h")
    assert pytest.approx(target - time.time(), abs=1.0) == 2 * 3600


def test_parse_until_days() -> None:
    target = parse_until("+1d")
    assert pytest.approx(target - time.time(), abs=1.0) == 86400


def test_parse_until_iso_with_z() -> None:
    target = parse_until("2030-01-01T00:00:00Z")
    expected = _dt.datetime(2030, 1, 1, tzinfo=_dt.UTC).timestamp()
    assert target == expected


def test_parse_until_iso_date_only() -> None:
    target = parse_until("2030-01-01")
    expected = _dt.datetime(2030, 1, 1, tzinfo=_dt.UTC).timestamp()
    assert target == expected


def test_parse_until_raw_seconds() -> None:
    assert parse_until("9999999999.0") == 9999999999.0


def test_parse_until_empty_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        parse_until("")


def test_parse_until_garbage_raises() -> None:
    with pytest.raises(ValueError, match="not understood"):
        parse_until("nonsense string")


# ---- format_remaining ----


def test_format_remaining_expired() -> None:
    assert format_remaining(0) == "expired"
    assert format_remaining(-100) == "expired"


def test_format_remaining_seconds_only() -> None:
    assert format_remaining(45) == "45s"


def test_format_remaining_mixed_units() -> None:
    assert format_remaining(86400 + 3600 * 2 + 60 * 15 + 7) == "1d 2h 15m 7s"


# ---- trust-evaluator bypass ----


def test_evaluate_trust_bypassed_when_autopilot_active() -> None:
    activate(time.time() + 3600)
    decision = evaluate_trust("run_shell")
    assert isinstance(decision, TrustDecision)
    assert decision.allowed is True
    assert decision.via_autopilot is True
    assert "autopilot" in decision.reason


def test_evaluate_trust_not_bypassed_when_autopilot_expired() -> None:
    """Expired window must NOT auto-allow; falls back to prompter (refuses non-TTY)."""
    activate(time.time() - 60)
    decision = evaluate_trust("run_shell")
    # Non-TTY default prompter refuses, so this is allowed=False.
    assert decision.via_autopilot is False
    assert decision.allowed is False


def test_evaluate_trust_grant_wins_over_autopilot() -> None:
    """An existing user-scope grant should mark the decision as grant, not autopilot."""
    from veles.core.trust_store import TrustStore, user_trust_path

    user_store = TrustStore.load(user_trust_path())
    user_store.grant("run_shell")
    activate(time.time() + 3600)
    decision = evaluate_trust("run_shell")
    assert decision.allowed is True
    assert decision.via_autopilot is False
    assert "user-scope" in decision.reason
