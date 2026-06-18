"""M170 — `veles run` verify→escalate wiring.

Covers the CLI-side glue around the (separately-tested) pure core:
evidence rendering from history, buffered-output suppression, and the
decision/print/rebind logic in `_maybe_verify_and_escalate`.
"""

from __future__ import annotations

import argparse

from veles.cli.commands.run import (
    _maybe_verify_and_escalate,
    _render_evidence,
    _verify_enabled,
)
from veles.core.verify import VerifyVerdict


class _FakeResult:
    def __init__(self, text, *, history=None, session_id="s1"):
        self.text = text
        self.history = history or []
        self.session_id = session_id
        self.stopped_reason = "completed"
        self.iterations = 1


def _args(**kw):
    base = {"verify": True, "provider": "ollama", "model": "m", "prompt": "q"}
    base.update(kw)
    return argparse.Namespace(**base)


# ---- evidence rendering ----


def test_render_evidence_includes_calls_and_results():
    from veles.core.provider import Message, ToolCall

    history = [
        Message(
            role="assistant",
            tool_calls=[ToolCall(id="1", name="run_shell", arguments={"command": "ls"})],
        ),
        Message(role="tool", content="file1\nfile2", tool_call_id="1"),
    ]
    ev = _render_evidence(history)
    assert "run_shell" in ev
    assert "command='ls'" in ev
    assert "file1" in ev


def test_render_evidence_truncates():
    from veles.core.provider import Message

    history = [Message(role="tool", content="x" * 9000, tool_call_id="1")]
    assert len(_render_evidence(history, max_chars=100)) <= 100


# ---- flag gating ----


def test_verify_enabled_flag_and_env(monkeypatch):
    monkeypatch.delenv("VELES_VERIFY_MODE", raising=False)
    assert _verify_enabled(_args(verify=True)) is True
    assert _verify_enabled(_args(verify=False)) is False
    monkeypatch.setenv("VELES_VERIFY_MODE", "1")
    assert _verify_enabled(_args(verify=False)) is True


def test_disabled_returns_base_unchanged(monkeypatch):
    monkeypatch.delenv("VELES_VERIFY_MODE", raising=False)
    base = _FakeResult("answer")
    out = _maybe_verify_and_escalate(_args(verify=False), object(), base, store=None)
    assert out is base


# ---- decision paths ----


def test_pass_keeps_base_and_never_escalates(monkeypatch):
    import veles.cli.commands.run as runmod
    import veles.core.routing as rmod
    import veles.core.verify as vmod

    monkeypatch.setattr(vmod, "advisor_verifier", lambda p, a, evidence="": (VerifyVerdict.PASS, []))
    monkeypatch.setattr(rmod, "route", lambda task, project: ("claude-cli", "sonnet"))
    invoked = []
    monkeypatch.setattr(
        runmod,
        "_build_escalator",
        lambda *a, **k: (lambda prompt: invoked.append(1) or _FakeResult("ESC")),
    )
    base = _FakeResult("good answer")
    out = _maybe_verify_and_escalate(_args(), object(), base, store=None)
    assert out is base
    assert invoked == []  # PASS must not call the escalator


def test_unknown_keeps_base(monkeypatch):
    import veles.core.routing as rmod
    import veles.core.verify as vmod

    monkeypatch.setattr(
        vmod, "advisor_verifier", lambda p, a, evidence="": (VerifyVerdict.UNKNOWN, [])
    )
    monkeypatch.setattr(rmod, "route", lambda task, project: ("claude-cli", "sonnet"))
    base = _FakeResult("answer")
    out = _maybe_verify_and_escalate(_args(), object(), base, store=None)
    assert out is base


def test_fail_escalates_and_rebinds(monkeypatch):
    import veles.cli.commands.run as runmod
    import veles.core.routing as rmod
    import veles.core.verify as vmod

    monkeypatch.setattr(
        vmod, "advisor_verifier", lambda p, a, evidence="": (VerifyVerdict.FAIL, ["hallucinated"])
    )
    monkeypatch.setattr(rmod, "route", lambda task, project: ("claude-cli", "sonnet"))
    escalated = _FakeResult("STRONG ANSWER", session_id="s2")
    monkeypatch.setattr(runmod, "_build_escalator", lambda *a, **k: (lambda prompt: escalated))
    base = _FakeResult("weak answer")
    out = _maybe_verify_and_escalate(_args(), object(), base, store=None)
    assert out is escalated  # printed answer + hooks use the corrected run


def test_fail_with_same_advisor_model_warns_and_keeps_base(monkeypatch, capsys):
    import veles.core.routing as rmod
    import veles.core.verify as vmod

    monkeypatch.setattr(vmod, "advisor_verifier", lambda p, a, evidence="": (VerifyVerdict.FAIL, ["x"]))
    # advisor route resolves to the SAME provider/model as the base run.
    monkeypatch.setattr(rmod, "route", lambda task, project: ("ollama", "m"))
    base = _FakeResult("weak")
    out = _maybe_verify_and_escalate(_args(provider="ollama", model="m"), object(), base, store=None)
    assert out is base  # no distinct stronger model → no escalation
    assert "equals the base model" in capsys.readouterr().err


# ---- buffered-output suppression ----


def test_emit_output_false_suppresses_print(capsys):
    from veles.cli import _run_agent_streaming_aware

    class _StubAgent:
        def run(self, prompt, on_text_delta=None):
            return _FakeResult("HELLO")

    args = argparse.Namespace(stream=False, max_tokens_total=0, provider="ollama")
    _run_agent_streaming_aware(_StubAgent(), "q", args, emit_output=False)
    assert capsys.readouterr().out == ""
    _run_agent_streaming_aware(_StubAgent(), "q", args, emit_output=True)
    assert "HELLO" in capsys.readouterr().out
