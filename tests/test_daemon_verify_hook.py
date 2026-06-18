"""M170b — daemon verify→escalate wiring.

Two layers: `run_agent_in_background` runs the injected `verify_hook` before
the `completed` event and rebinds the result; `_make_verify_hook` builds the
real daemon hook (gate + advisor verdict + escalation on the BASE session_id
for chat continuity).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import veles.daemon.agent_factory as af
from veles.core.agent import RunResult
from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.core.verify import VerifyVerdict
from veles.daemon.runner import new_run_handle, run_agent_in_background


class _StubAgent:
    def __init__(self, result):
        self._r = result

    def run(self, prompt, on_text_delta=None):
        return self._r


def _daemon_args():
    # _factory_settings_from_args resolves provider/model from config when these
    # are None; the rest of the fields fall through getattr defaults.
    return argparse.Namespace(provider=None, model=None)


def _project_with_provider(tmp_path: Path, *, extra: str = ""):
    project = init_project(tmp_path, name=None, force=False)
    (project.state_dir / "config.toml").write_text(
        f'[provider]\ndefault = "ollama"\nmodel = "base-m"\n{extra}',
        encoding="utf-8",
    )
    return project


# ---- runner integration ----


async def test_verify_hook_rebinds_completed_result():
    base = RunResult(text="weak", iterations=1, session_id="s1")
    strong = RunResult(text="strong", iterations=2, session_id="s1")
    handle = new_run_handle(session_id="s1")
    seen = {}

    def hook(prompt, result):
        seen["prompt"] = prompt
        seen["base"] = result
        return strong

    await run_agent_in_background(handle, agent=_StubAgent(base), prompt="q", verify_hook=hook)

    assert seen["base"] is base
    # final_text is what the `completed` event (and the channel) renders; set
    # directly from the rebound result on runner.py.
    assert handle.final_text == "strong"
    assert handle.state == "completed"


async def test_no_verify_hook_keeps_base():
    base = RunResult(text="base", iterations=1, session_id="s1")
    handle = new_run_handle(session_id="s1")
    await run_agent_in_background(handle, agent=_StubAgent(base), prompt="q", verify_hook=None)
    assert handle.final_text == "base"


async def test_verify_hook_failure_keeps_base():
    """Best-effort: a raising hook must not wedge the turn."""
    base = RunResult(text="base", iterations=1, session_id="s1")
    handle = new_run_handle(session_id="s1")

    def hook(prompt, result):
        raise RuntimeError("advisor down")

    await run_agent_in_background(handle, agent=_StubAgent(base), prompt="q", verify_hook=hook)
    assert handle.final_text == "base"
    assert handle.state == "completed"


# ---- _make_verify_hook gate ----


def test_make_verify_hook_off_returns_none(monkeypatch, tmp_path):
    monkeypatch.delenv("VELES_VERIFY_MODE", raising=False)
    project = _project_with_provider(tmp_path)
    store = SessionStore(project.memory_db_path)
    try:
        assert (
            af._make_verify_hook(_daemon_args(), project=project, store=store, daemon_session=None)
            is None
        )
    finally:
        store.close()


def test_make_verify_hook_enabled_via_config(monkeypatch, tmp_path):
    monkeypatch.delenv("VELES_VERIFY_MODE", raising=False)
    project = _project_with_provider(tmp_path, extra="[verify]\nenabled = true\n")
    store = SessionStore(project.memory_db_path)
    try:
        hook = af._make_verify_hook(
            _daemon_args(), project=project, store=store, daemon_session=None
        )
        assert hook is not None
    finally:
        store.close()


# ---- _make_verify_hook decision + REAL escalator (continuity fix) ----


def test_make_verify_hook_escalates_on_base_session(monkeypatch, tmp_path):
    monkeypatch.setenv("VELES_VERIFY_MODE", "1")
    project = _project_with_provider(tmp_path)
    store = SessionStore(project.memory_db_path)
    try:
        import veles.core.routing as rmod
        import veles.core.verify as vmod

        monkeypatch.setattr(
            vmod, "advisor_verifier", lambda p, a, evidence="": (VerifyVerdict.FAIL, ["bad"])
        )
        monkeypatch.setattr(rmod, "route", lambda task, proj: ("anthropic", "strong-m"))

        captured = {}
        strong = RunResult(text="STRONG", iterations=2, session_id="sess-1")

        def fake_build(settings, *, project, store, session_id, prompt):
            captured["session_id"] = session_id
            captured["provider"] = settings.provider_name
            captured["model"] = settings.model
            return _StubAgent(strong)

        monkeypatch.setattr(af, "_build_agent_for_turn", fake_build)

        hook = af._make_verify_hook(
            _daemon_args(), project=project, store=store, daemon_session=None
        )
        assert hook is not None
        base = RunResult(text="weak", iterations=1, session_id="sess-1")
        out = hook("question", base)

        assert out is strong
        assert captured["session_id"] == "sess-1"  # continuity: base chat session reused
        assert captured["provider"] == "anthropic"
        assert captured["model"] == "strong-m"
    finally:
        store.close()


def test_make_verify_hook_same_model_no_escalation(monkeypatch, tmp_path):
    monkeypatch.setenv("VELES_VERIFY_MODE", "1")
    project = _project_with_provider(tmp_path)
    store = SessionStore(project.memory_db_path)
    try:
        import veles.core.routing as rmod
        import veles.core.verify as vmod

        monkeypatch.setattr(
            vmod, "advisor_verifier", lambda p, a, evidence="": (VerifyVerdict.FAIL, ["x"])
        )
        # advisor route resolves to the SAME provider/model as the daemon base.
        monkeypatch.setattr(rmod, "route", lambda task, proj: ("ollama", "base-m"))

        hook = af._make_verify_hook(
            _daemon_args(), project=project, store=store, daemon_session=None
        )
        base = RunResult(text="weak", iterations=1, session_id="s1")
        assert hook("q", base) is base  # no distinct stronger model → keep base
    finally:
        store.close()
