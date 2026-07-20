"""M170 — `veles run` verify→escalate wiring.

Covers the CLI-side glue around the (separately-tested) pure core:
evidence rendering from history, buffered-output suppression, and the
decision/print/rebind logic in `_maybe_verify_and_escalate`.
"""

from __future__ import annotations

import argparse

from veles.cli.commands.run import (
    _build_escalator,
    _maybe_verify_and_escalate,
    _verify_enabled,
)
from veles.core.verify import VerifyVerdict, render_evidence


class _FakeResult:
    def __init__(self, text, *, history=None, session_id="s1"):
        self.text = text
        self.history = history or []
        self.session_id = session_id
        self.stopped_reason = "completed"
        self.iterations = 1


def _args(**kw):
    base = {
        "verify": True,
        "provider": "ollama",
        "model": "m",
        "prompt": "q",
        "max_tokens_total": 0,
        "stream": False,
    }
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
    ev = render_evidence(history)
    assert "run_shell" in ev
    assert "command='ls'" in ev
    assert "file1" in ev


def test_render_evidence_truncates():
    from veles.core.provider import Message

    history = [Message(role="tool", content="x" * 9000, tool_call_id="1")]
    assert len(render_evidence(history, max_chars=100)) <= 100


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

    monkeypatch.setattr(
        vmod, "advisor_verifier", lambda p, a, evidence="": (VerifyVerdict.PASS, [])
    )
    monkeypatch.setattr(rmod, "route", lambda task, project: ("claude-cli", "sonnet"))
    invoked = []
    monkeypatch.setattr(
        runmod,
        "_build_escalator",
        lambda *a, **k: lambda prompt: invoked.append(1) or _FakeResult("ESC"),
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
    monkeypatch.setattr(runmod, "_build_escalator", lambda *a, **k: lambda prompt: escalated)
    base = _FakeResult("weak answer")
    out = _maybe_verify_and_escalate(_args(), object(), base, store=None)
    assert out is escalated  # printed answer + hooks use the corrected run


def test_fail_with_same_advisor_model_warns_and_keeps_base(monkeypatch, capsys):
    import veles.core.routing as rmod
    import veles.core.verify as vmod

    monkeypatch.setattr(
        vmod, "advisor_verifier", lambda p, a, evidence="": (VerifyVerdict.FAIL, ["x"])
    )
    # advisor route resolves to the SAME provider/model as the base run.
    monkeypatch.setattr(rmod, "route", lambda task, project: ("ollama", "m"))
    base = _FakeResult("weak")
    out = _maybe_verify_and_escalate(
        _args(provider="ollama", model="m"), object(), base, store=None
    )
    assert out is base  # no distinct stronger model → no escalation
    assert "equals the base model" in capsys.readouterr().err


# ---- escalator mechanism (the real _build_escalator body) ----


def test_build_escalator_runs_on_advisor_route_and_returns_result(monkeypatch):
    """Exercise the REAL _build_escalator: it must build the agent on the
    advisor provider/model with the run toolset and run it buffered."""
    import veles.cli as cli

    stub_result = _FakeResult("STRONGER ANSWER", session_id="esc")
    captured = {}

    class _StubAgent:
        def run(self, prompt, on_text_delta=None, event_listener=None):
            captured["prompt"] = prompt
            return stub_result

    def fake_build(args, project, **kw):
        captured["provider"] = args.provider
        captured["model"] = args.model
        captured["tool_aware"] = kw.get("tool_aware")
        return _StubAgent()

    monkeypatch.setattr(cli, "build_command_agent", fake_build)
    monkeypatch.setattr(cli, "_build_run_system_prompt", lambda a, p: "")

    esc = _build_escalator(_args(), object(), "claude-cli", "sonnet", store=None)
    out = esc("redo this")

    assert out is stub_result
    assert captured["prompt"] == "redo this"
    assert captured["provider"] == "claude-cli"
    assert captured["model"] == "sonnet"
    assert captured["tool_aware"] is True  # cli-delegate → MCP-bridged tools


def test_build_escalator_tool_aware_false_for_direct_provider(monkeypatch):
    import veles.cli as cli

    captured = {}

    class _StubAgent:
        def run(self, prompt, on_text_delta=None, event_listener=None):
            return _FakeResult("x")

    def fake_build(args, project, **kw):
        captured["tool_aware"] = kw.get("tool_aware")
        return _StubAgent()

    monkeypatch.setattr(cli, "build_command_agent", fake_build)
    monkeypatch.setattr(cli, "_build_run_system_prompt", lambda a, p: "")

    _build_escalator(_args(), object(), "anthropic", "claude-x", store=None)("p")
    assert captured["tool_aware"] is False


def test_build_escalator_returns_none_when_agent_unbuildable(monkeypatch):
    """Missing key etc. → build_command_agent returns None → escalator None,
    which the caller treats as 'no escalation route' (keeps the base answer)."""
    import veles.cli as cli

    monkeypatch.setattr(cli, "build_command_agent", lambda *a, **k: None)
    monkeypatch.setattr(cli, "_build_run_system_prompt", lambda a, p: "")

    esc = _build_escalator(_args(), object(), "claude-cli", "sonnet", store=None)
    assert esc("p") is None


# ---- buffered-output suppression ----


def test_emit_output_false_suppresses_print(capsys):
    from veles.cli import _run_agent_streaming_aware

    class _StubAgent:
        def run(self, prompt, on_text_delta=None, event_listener=None):
            return _FakeResult("HELLO")

    args = argparse.Namespace(stream=False, max_tokens_total=0, provider="ollama")
    _run_agent_streaming_aware(_StubAgent(), "q", args, emit_output=False)
    assert capsys.readouterr().out == ""
    _run_agent_streaming_aware(_StubAgent(), "q", args, emit_output=True)
    assert "HELLO" in capsys.readouterr().out
