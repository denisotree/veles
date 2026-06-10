"""M106: BootstrapStep skips its ConfirmScreen when the first-run wizard
already collected an affirmative 'initialize here?' answer, eliminating
the duplicate Y/N prompt the user previously had to answer twice."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from veles.tui.wizard.project_steps import BootstrapStep
from veles.tui.wizard.screens import ConfirmScreen
from veles.tui.wizard.step import WizardContext, WizardOutcome


class _RecordingApp:
    """Stand-in for the Textual App that records push_screen_wait calls."""

    def __init__(self, default_answer: Any = None) -> None:
        self.pushed: list[Any] = []
        self._answer = default_answer

    async def push_screen_wait(self, screen):  # noqa: D401
        self.pushed.append(screen)
        return self._answer


async def test_bootstrap_skips_confirm_when_flag_set(tmp_path: Path) -> None:
    app = _RecordingApp()
    ctx = WizardContext(app=app, answers={"_skip_bootstrap_confirm": True})
    step = BootstrapStep(cwd=tmp_path)

    outcome = await step.run(ctx)

    assert outcome is WizardOutcome.NEXT
    # No confirm screen was shown — the user already answered Yes upstream.
    assert app.pushed == []
    # init_project ran and the project object is in answers.
    assert "project" in ctx.answers
    assert ctx.answers["project"].root == tmp_path


async def test_bootstrap_shows_confirm_when_flag_absent(tmp_path: Path) -> None:
    app = _RecordingApp(default_answer=True)
    ctx = WizardContext(app=app, answers={})
    step = BootstrapStep(cwd=tmp_path)

    outcome = await step.run(ctx)

    assert outcome is WizardOutcome.NEXT
    # One ConfirmScreen was pushed.
    assert len(app.pushed) == 1
    assert isinstance(app.pushed[0], ConfirmScreen)
    assert "project" in ctx.answers


def test_run_project_wizard_tui_seeds_skip_flag(monkeypatch, tmp_path: Path) -> None:
    """run_project_wizard_tui forwards skip_bootstrap_confirm into the
    WizardApp's initial answers dict so BootstrapStep sees it."""
    from veles.tui.wizard import project_runner as runner_mod

    captured: dict[str, Any] = {}

    class _FakeApp:
        def __init__(self, *, steps, initial=None, **_kwargs):
            captured["initial"] = dict(initial or {})

        def run(self):
            return None  # cancel — we only care about constructor args

    monkeypatch.setattr(runner_mod, "WizardApp", _FakeApp)

    runner_mod.run_project_wizard_tui(tmp_path, skip_bootstrap_confirm=True)
    assert captured["initial"].get("_skip_bootstrap_confirm") is True

    runner_mod.run_project_wizard_tui(tmp_path)
    assert captured["initial"] == {}


def test_maybe_run_first_run_wizard_sets_flag_on_yes(monkeypatch) -> None:
    """cli/wizard.py::maybe_run_first_run_wizard carries the user's Yes
    answer forward as args._wizard_init_project_here so the project
    wizard's BootstrapStep can skip its duplicate confirm."""
    import sys

    from veles.cli import wizard as wizard_mod

    monkeypatch.setattr(wizard_mod, "should_run_wizard", lambda _args: True)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True, raising=False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True, raising=False)

    def fake_tui():
        cfg = argparse.Namespace(default_provider="openrouter")
        return cfg, {"init_project_here": True}

    import veles.tui.wizard.user_runner as user_runner_mod

    monkeypatch.setattr(user_runner_mod, "run_user_wizard_tui", fake_tui)

    args = argparse.Namespace()
    wizard_mod.maybe_run_first_run_wizard(args)
    assert getattr(args, "_wizard_init_project_here", False) is True
    # The "No" branch flags must NOT be set.
    assert not getattr(args, "_wizard_user_chose_no_project", False)


def test_maybe_run_first_run_wizard_sets_no_flag_on_no(monkeypatch) -> None:
    import sys

    from veles.cli import wizard as wizard_mod

    monkeypatch.setattr(wizard_mod, "should_run_wizard", lambda _args: True)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True, raising=False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True, raising=False)

    def fake_tui():
        cfg = argparse.Namespace(default_provider="openrouter")
        return cfg, {"init_project_here": False}

    import veles.tui.wizard.user_runner as user_runner_mod

    monkeypatch.setattr(user_runner_mod, "run_user_wizard_tui", fake_tui)

    args = argparse.Namespace()
    wizard_mod.maybe_run_first_run_wizard(args)
    assert getattr(args, "no_wizard", False) is True
    assert getattr(args, "_wizard_user_chose_no_project", False) is True
    assert not getattr(args, "_wizard_init_project_here", False)
