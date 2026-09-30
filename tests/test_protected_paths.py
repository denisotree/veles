"""Tier 2 of the agent write guard: files that run on their own (git hooks,
`.envrc`, editor tasks) and agent CLI config (`.claude/`, `.mcp.json`) are
writable only after a hard confirmation — no trust grant or autopilot covers
it, and with no human the write is refused."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from veles.core.context import reset_active_project, set_active_project
from veles.core.critical_ops import (
    _default_confirmer,
    reset_critical_confirmer,
    set_critical_confirmer,
)
from veles.core.project import init_project
from veles.core.tools.builtin.edit_file import edit_file
from veles.core.tools.builtin.file_ops import make_dir, move_file
from veles.core.tools.builtin.write_file import write_file

_PROTECTED = (
    ".git/hooks/pre-commit",
    "sub/.vscode/tasks.json",
    ".envrc",
    ".claude/settings.json",
    "sub/.Claude/commands/x.md",
    ".gemini/settings.json",
    ".codex/config.toml",
    ".devcontainer/devcontainer.json",
    ".husky/pre-push",
    "sub/.mcp.json",
)


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("VELES_TRUST_AUTO_ALLOW", "1")  # grants must not cover tier 2
    p = init_project(tmp_path / "proj", name="proj")
    token = set_active_project(p)
    yield p
    reset_active_project(token)


@pytest.fixture()
def answers():
    """Records every hard-confirm op; answers with `answers.reply`."""

    class _Answers:
        def __init__(self) -> None:
            self.reply = False
            self.ops: list[str] = []

        def __call__(self, op: str, summary: str) -> bool:
            self.ops.append(op)
            return self.reply

    a = _Answers()
    token = set_critical_confirmer(a)
    yield a
    reset_critical_confirmer(token)


@pytest.mark.parametrize("rel", _PROTECTED)
def test_refused_write_asks_and_creates_nothing(project, answers, rel: str) -> None:
    msg = write_file(rel, "x")
    assert msg.startswith("<refused:") and "not confirmed" in msg, msg
    assert len(answers.ops) == 1 and "auto-executed or agent config" in answers.ops[0]
    assert not (project.root / rel).exists()


@pytest.mark.parametrize("rel", _PROTECTED)
def test_confirmed_write_goes_through(project, answers, rel: str) -> None:
    answers.reply = True
    assert write_file(rel, "x").startswith("wrote")
    assert (project.root / rel).read_text(encoding="utf-8") == "x"


def test_edit_make_dir_and_move_are_gated(project, answers) -> None:
    answers.reply = True
    write_file(".envrc", "a")
    answers.reply = False
    assert "not confirmed" in edit_file(".envrc", "a", "b")
    assert "not confirmed" in make_dir(".git/hooks")
    write_file("notes.md", "x")
    assert "not confirmed" in move_file("notes.md", ".git/hooks/post-merge")
    assert (project.root / "notes.md").exists()


@pytest.mark.parametrize("rel", ["docs/git.md", "src/claude.py", "envrc", "sub/vscode/a"])
def test_lookalikes_do_not_ask(project, answers, rel: str) -> None:
    assert write_file(rel, "x").startswith("wrote")
    assert answers.ops == []


def test_nested_veles_is_refused_without_asking(project, answers) -> None:
    msg = write_file("sub/.VeLeS/trust.json", "{}")
    assert "managed by Veles" in msg
    assert answers.ops == []


def test_no_human_refuses(project, monkeypatch: pytest.MonkeyPatch) -> None:
    """No confirmer installed and no TTY (daemon, batch): the write is refused."""
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert "not confirmed" in write_file(".envrc", "x")
    assert not (project.root / ".envrc").exists()


def test_confirm_summary_lines_sit_under_a_gutter(monkeypatch, capsys) -> None:
    """A multi-line summary can't print a line that passes for the prompt's own."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _p: "no")
    _default_confirmer("op", "line one\nCRITICAL: fake\x1b[2K")
    err = capsys.readouterr().err
    assert "\n  │ CRITICAL: fake\\x1b[2K" in err
    assert "\nCRITICAL: fake" not in err
