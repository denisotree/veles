"""M47 — first-run wizard: gating, prompter, persistence."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from veles.cli.wizard import (
    maybe_run_first_run_wizard,
    reset_wizard_prompter,
    run_wizard,
    set_wizard_prompter,
    should_run_wizard,
)
from veles.core.user_config import load_user_config, user_config_path

# ---------- harness ----------


@pytest.fixture(autouse=True)
def _isolated_user_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("VELES_USER_HOME", str(home))
    monkeypatch.delenv("VELES_NO_WIZARD", raising=False)
    return home


def _ns(**kw) -> argparse.Namespace:
    args = argparse.Namespace()
    args.command = kw.pop("command", "run")
    args.no_wizard = kw.pop("no_wizard", False)
    for k, v in kw.items():
        setattr(args, k, v)
    return args


class _ScriptedPrompter:
    """Replays a list of canned answers in order."""

    def __init__(self, answers: list[str]) -> None:
        self._answers = list(answers)
        self.calls: list[tuple[str, str | None]] = []

    def __call__(self, prompt: str, default: str | None) -> str:
        self.calls.append((prompt, default))
        if not self._answers:
            return default or ""
        return self._answers.pop(0)


# ---------- should_run_wizard gate ----------


def test_gate_skips_when_no_wizard_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    assert should_run_wizard(_ns(no_wizard=True)) is False


def test_gate_skips_when_env_var_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setenv("VELES_NO_WIZARD", "1")
    assert should_run_wizard(_ns()) is False


def test_gate_skips_for_init_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    assert should_run_wizard(_ns(command="init")) is False


def test_gate_skips_for_import_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    assert should_run_wizard(_ns(command="import")) is False


def test_gate_skips_in_non_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert should_run_wizard(_ns()) is False


def test_gate_skips_when_config_already_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    p = user_config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('[user]\nlanguage = "en"\ndefault_provider = "openrouter"\n', encoding="utf-8")
    assert should_run_wizard(_ns()) is False


def test_gate_passes_when_all_conditions_met(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    assert should_run_wizard(_ns()) is True


# ---------- run_wizard with stub prompter ----------


def test_wizard_writes_config_with_defaults() -> None:
    prompter = _ScriptedPrompter(["", "", ""])  # accept defaults
    token = set_wizard_prompter(prompter)
    try:
        result = run_wizard()
    finally:
        reset_wizard_prompter(token)
    assert result.config.language == "en"
    assert result.config.default_provider == "openrouter"
    assert result.config.first_project_name is None
    loaded = load_user_config()
    assert loaded == result.config


def test_wizard_accepts_explicit_choices() -> None:
    prompter = _ScriptedPrompter(["ru", "anthropic", "myorg"])
    token = set_wizard_prompter(prompter)
    try:
        result = run_wizard()
    finally:
        reset_wizard_prompter(token)
    assert result.config.language == "ru"
    assert result.config.default_provider == "anthropic"
    assert result.config.first_project_name == "myorg"


def test_wizard_re_prompts_on_invalid_choice() -> None:
    """First answer is rejected; second answer accepted."""
    prompter = _ScriptedPrompter(["bogus", "ru", "openai", ""])
    token = set_wizard_prompter(prompter)
    try:
        result = run_wizard()
    finally:
        reset_wizard_prompter(token)
    assert result.config.language == "ru"
    assert result.config.default_provider == "openai"
    # Verify the prompter was actually called >1 times for the language step.
    language_calls = [c for c in prompter.calls if "language" in c[0].lower()]
    assert len(language_calls) >= 2


def test_wizard_persists_to_disk() -> None:
    prompter = _ScriptedPrompter(["en", "openrouter", ""])
    token = set_wizard_prompter(prompter)
    try:
        run_wizard()
    finally:
        reset_wizard_prompter(token)
    assert user_config_path().is_file()


# ---------- maybe_run_first_run_wizard integration ----------


def test_maybe_runs_wizard_when_gate_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    prompter = _ScriptedPrompter(["", "", ""])
    token = set_wizard_prompter(prompter)
    try:
        maybe_run_first_run_wizard(_ns())
    finally:
        reset_wizard_prompter(token)
    assert user_config_path().is_file()


def test_maybe_skips_wizard_when_gate_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    def boom(_p, _d):
        raise AssertionError("prompter should not run when gate blocks")

    token = set_wizard_prompter(boom)
    try:
        maybe_run_first_run_wizard(_ns(no_wizard=True))
    finally:
        reset_wizard_prompter(token)
    assert not user_config_path().is_file()


def test_maybe_swallows_prompter_exceptions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Wizard failure is best-effort: stderr warning, no propagation."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    def angry(_p, _d):
        raise RuntimeError("prompter blew up")

    token = set_wizard_prompter(angry)
    try:
        maybe_run_first_run_wizard(_ns())  # must not raise
    finally:
        reset_wizard_prompter(token)


def test_maybe_handles_keyboard_interrupt_gracefully(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    def cancel(_p, _d):
        raise KeyboardInterrupt

    token = set_wizard_prompter(cancel)
    try:
        maybe_run_first_run_wizard(_ns())
    finally:
        reset_wizard_prompter(token)
    assert not user_config_path().is_file()
