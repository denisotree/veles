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
from veles.core.tools.builtin.file_ops import delete_file, make_dir, move_file
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
    ".githooks/pre-commit",
    ".pre-commit-config.yaml",
    "lefthook.yml",
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


def test_delete_and_move_out_of_git_are_gated(project, answers) -> None:
    hook = project.root / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(parents=True)
    hook.write_text("#!/bin/sh\n", encoding="utf-8")
    assert "<refused" in delete_file(".git/hooks/pre-commit")
    assert "<refused" in move_file(".git/hooks/pre-commit", "notes.md")
    assert hook.exists() and not (project.root / "notes.md").exists()


def test_innocent_symlink_into_git_hooks_is_gated(project, answers) -> None:
    """The guard sees the resolved path, so a link named `docs` into `.git/hooks`
    doesn't slip a hook past it."""
    (project.root / ".git" / "hooks").mkdir(parents=True)
    (project.root / "docs").symlink_to(project.root / ".git" / "hooks")
    assert "not confirmed" in write_file("docs/pre-commit", "x")
    assert not (project.root / ".git" / "hooks" / "pre-commit").exists()


def test_symlinked_git_dir_is_still_protected(project, answers) -> None:
    """`.git` linked to a plainly named dir: both spellings of a hook are gated."""
    real = project.root / "gitdata" / "hooks"
    real.mkdir(parents=True)
    (project.root / ".git").symlink_to(project.root / "gitdata")
    assert "not confirmed" in write_file(".git/hooks/pre-commit", "x")
    assert "not confirmed" in write_file("gitdata/hooks/pre-commit", "x")
    assert not (real / "pre-commit").exists()


def test_custom_hooks_path_is_protected(project, answers) -> None:
    (project.root / ".git").mkdir()
    (project.root / ".git" / "config").write_text(
        '[core]\n\thooksPath = tools/hooks\n[remote "origin"]\n\turl = x\n', encoding="utf-8"
    )
    assert "not confirmed" in write_file("tools/hooks/pre-commit", "x")
    assert write_file("tools/other.py", "x").startswith("wrote")


@pytest.mark.parametrize("value", ["~nosuchuser_zz/hooks", "bad\x00path"])
def test_bad_hooks_path_value_does_not_break_writes(project, answers, value: str) -> None:
    (project.root / ".git").mkdir()
    (project.root / ".git" / "config").write_text(
        f"[core]\n\thooksPath = {value}\n", encoding="utf-8"
    )
    assert write_file("notes.md", "x").startswith("wrote")


def test_hooks_path_with_quotes_and_comment_is_protected(project, answers) -> None:
    (project.root / ".git").mkdir()
    (project.root / ".git" / "config").write_text(
        '[core]\n\tbare\n\thooksPath = "tools/hooks" ; set by setup.sh\n', encoding="utf-8"
    )
    assert "not confirmed" in write_file("tools/hooks/pre-commit", "x")


def _git(*args: str, cwd: Path) -> None:
    import subprocess

    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def test_hooks_path_of_an_enclosing_repo_is_protected(tmp_path, monkeypatch, answers) -> None:
    """The project is a subdirectory of the git repo; the repo's config, not a
    `.git/config` under the project, sets the hooks dir."""
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-q", cwd=repo)
    _git("config", "core.hooksPath", "proj/hooks", cwd=repo)
    p = init_project(repo / "proj", name="proj")
    token = set_active_project(p)
    try:
        assert "not confirmed" in write_file("hooks/pre-commit", "x")
        assert write_file("notes.md", "x").startswith("wrote")
    finally:
        reset_active_project(token)


def test_hooks_path_with_a_git_file_is_protected(tmp_path, monkeypatch, answers) -> None:
    """`.git` is a `gitdir:` file (worktree / separate git dir)."""
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    proj = tmp_path / "proj"
    _git("init", "-q", f"--separate-git-dir={tmp_path / 'gitdata'}", str(proj), cwd=tmp_path)
    _git("config", "core.hooksPath", "tools/hooks", cwd=proj)
    p = init_project(proj, name="proj")
    token = set_active_project(p)
    try:
        assert "not confirmed" in write_file("tools/hooks/pre-commit", "x")
    finally:
        reset_active_project(token)


def test_global_hooks_path_is_protected(tmp_path, monkeypatch, answers) -> None:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    proj = tmp_path / "proj"
    proj.mkdir()
    _git("init", "-q", cwd=proj)
    global_cfg = tmp_path / "gitconfig"
    global_cfg.write_text(f"[core]\n\thooksPath = {proj / 'gh'}\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_cfg))
    p = init_project(proj, name="proj")
    token = set_active_project(p)
    try:
        assert "not confirmed" in write_file("gh/pre-commit", "x")
    finally:
        reset_active_project(token)


def test_unreadable_git_config_is_ignored(project, answers) -> None:
    (project.root / ".git").mkdir()
    (project.root / ".git" / "config").write_bytes(b"\xff\xfe[[[ not ini")
    assert write_file("notes.md", "x").startswith("wrote")
    assert answers.ops == []


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
