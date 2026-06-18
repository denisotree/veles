"""M170 — verify→escalate seam: pure decision + 3-state judge parsing.

The core is injection-based (verifier + escalator passed in) so the same
decision drives `veles run` and the daemon. Critical invariant: only a
CONFIDENT FAIL escalates; UNKNOWN (advisor unavailable OR unparseable judge
output) passes through, so a flaky judge can't trigger an expensive tier-1
re-run it never actually called for.
"""

from __future__ import annotations

from veles.core.verify import (
    VerifyVerdict,
    _parse_judge,
    advisor_verifier,
    verify_and_maybe_escalate,
)


# ---- pure decision logic ----


def _verifier(verdict: VerifyVerdict, concerns=None):
    return lambda _p, _a: (verdict, concerns or [])


def test_pass_keeps_answer_no_escalation():
    out = verify_and_maybe_escalate(
        "q", "a", verifier=_verifier(VerifyVerdict.PASS), escalator=lambda _p: "ESC"
    )
    assert out.verdict is VerifyVerdict.PASS
    assert out.escalated is False
    assert out.escalated_result is None


def test_unknown_passes_through_never_escalates():
    """The cost guard: a flaky/unavailable judge must not re-run tier-1."""
    called = []
    out = verify_and_maybe_escalate(
        "q",
        "a",
        verifier=_verifier(VerifyVerdict.UNKNOWN),
        escalator=lambda p: called.append(p) or "ESC",
    )
    assert out.verdict is VerifyVerdict.UNKNOWN
    assert out.escalated is False
    assert called == []  # escalator never invoked


def test_fail_escalates_and_carries_result():
    out = verify_and_maybe_escalate(
        "redo this",
        "bad answer",
        verifier=_verifier(VerifyVerdict.FAIL, ["hallucinated value"]),
        escalator=lambda p: f"STRONG[{p}]",
    )
    assert out.verdict is VerifyVerdict.FAIL
    assert out.escalated is True
    assert out.escalated_result == "STRONG[redo this]"
    assert out.concerns == ["hallucinated value"]


def test_fail_without_escalator_flags_only():
    out = verify_and_maybe_escalate(
        "q", "a", verifier=_verifier(VerifyVerdict.FAIL, ["x"]), escalator=None
    )
    assert out.verdict is VerifyVerdict.FAIL
    assert out.escalated is False
    assert out.escalated_result is None
    assert out.concerns == ["x"]


# ---- 3-state judge parsing ----


def test_parse_ok_true_is_pass():
    assert _parse_judge('{"ok": true}') == (VerifyVerdict.PASS, [])


def test_parse_ok_false_is_fail_with_concerns():
    assert _parse_judge('{"ok": false, "concerns": ["a", "b"]}') == (
        VerifyVerdict.FAIL,
        ["a", "b"],
    )


def test_parse_malformed_json_is_unknown():
    assert _parse_judge("not json at all") == (VerifyVerdict.UNKNOWN, [])


def test_parse_missing_ok_key_is_unknown():
    """A judge that answered the wrong shape is UNKNOWN, not FAIL."""
    assert _parse_judge('{"concerns": ["x"]}') == (VerifyVerdict.UNKNOWN, [])


def test_parse_empty_is_unknown():
    assert _parse_judge("") == (VerifyVerdict.UNKNOWN, [])


def test_parse_fenced_json():
    assert _parse_judge('```json\n{"ok": true}\n```') == (VerifyVerdict.PASS, [])


# ---- advisor_verifier maps sentinels to UNKNOWN ----


def test_advisor_verifier_unavailable_is_unknown(monkeypatch):
    import veles.core.verify as v

    monkeypatch.setattr(
        v, "call_advisor", lambda body, system_prompt=None: "<advisor unavailable: no key>"
    )
    assert advisor_verifier("q", "a") == (VerifyVerdict.UNKNOWN, [])


def test_advisor_verifier_failed_is_unknown(monkeypatch):
    import veles.core.verify as v

    monkeypatch.setattr(
        v, "call_advisor", lambda body, system_prompt=None: "<advisor failed: Timeout>"
    )
    assert advisor_verifier("q", "a") == (VerifyVerdict.UNKNOWN, [])


def test_advisor_verifier_passes_evidence_to_judge(monkeypatch):
    import veles.core.verify as v

    seen = {}

    def fake(body, system_prompt=None):
        seen["body"] = body
        return '{"ok": false, "concerns": ["unsupported"]}'

    monkeypatch.setattr(v, "call_advisor", fake)
    verdict, concerns = advisor_verifier("what is X?", "X is 42", evidence="query -> X=7")
    assert verdict is VerifyVerdict.FAIL
    assert concerns == ["unsupported"]
    # the evidence trace must reach the judge so it can catch grounding errors
    assert "query -> X=7" in seen["body"]
    assert "X is 42" in seen["body"]
