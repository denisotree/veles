"""Release F end to end: run_shell under the real OS sandbox (skipped where none works —
there the warning path is checked instead)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from veles.core import sandbox
from veles.core.context import reset_active_project, set_active_project
from veles.core.project import Project, init_project
from veles.core.tools.builtin.run_shell import run_shell

active = sandbox._probe().active
needs_sandbox = pytest.mark.skipif(not active, reason="no OS sandbox on this machine")


def _shell(project: Project | None, cmd: str) -> str:
    token = set_active_project(project)
    try:
        return run_shell(cmd)
    finally:
        reset_active_project(token)


@pytest.fixture
def repo(tmp_path: Path) -> Project:
    project = init_project(tmp_path / "p", name="p")
    subprocess.run(["git", "init", "-q", str(project.root)], check=True)
    return project


@needs_sandbox
def test_project_files_and_git_commit_work(repo: Project) -> None:
    out = _shell(
        repo,
        "echo x > a.txt && git add a.txt && git -c user.name=t -c user.email=t@t commit -qm m",
    )
    assert out.rstrip().endswith("<exit 0>")


@needs_sandbox
def test_hooks_config_and_state_are_read_only(repo: Project) -> None:
    for cmd in (
        "echo x > .git/hooks/pre-commit",
        "echo x >> .git/config",
        "echo x >> .veles/config.toml",
        "mv .git .git2",
    ):
        assert "<exit 0>" not in _shell(repo, cmd), cmd
    assert not (repo.root / ".git" / "hooks" / "pre-commit").exists()
    assert (repo.root / ".git").is_dir()


@needs_sandbox
def test_denied_write_gets_the_hint(repo: Project) -> None:
    assert "read-only for the agent's shell" in _shell(repo, "echo x >> .git/config")


@needs_sandbox
def test_agent_dirs_stay_writable(repo: Project) -> None:
    out = _shell(repo, "mkdir -p .veles/tmp && echo x > .veles/tmp/x")
    assert out.rstrip().endswith("<exit 0>")


@needs_sandbox
def test_new_envrc(repo: Project, capsys) -> None:
    out = _shell(repo, "echo x > .envrc")
    if sys.platform == "darwin":
        assert "<exit 0>" not in out and not (repo.root / ".envrc").exists()
    else:  # bwrap can't bind a missing path: reported instead
        assert "created .envrc" in out and ".envrc" in capsys.readouterr().err


@needs_sandbox
@pytest.mark.skipif(sys.platform != "darwin", reason="case-insensitive volume")
def test_case_variant_is_blocked(repo: Project) -> None:
    assert "<exit 0>" not in _shell(repo, "mkdir -p sub && echo x > sub/.ENVRC")


@needs_sandbox
def test_odd_root_name_is_protected(tmp_path: Path) -> None:
    project = init_project(tmp_path / 'my "odd" dir', name="p")
    subprocess.run(["git", "init", "-q", str(project.root)], check=True)
    assert "<exit 0>" not in _shell(project, "echo x > .git/hooks/pre-commit")
    assert _shell(project, "echo x > ok.txt").rstrip().endswith("<exit 0>")


@needs_sandbox
def test_project_under_a_symlink_is_protected(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    (tmp_path / "link").symlink_to(real, target_is_directory=True)
    project = init_project(tmp_path / "link" / "p", name="p")
    subprocess.run(["git", "init", "-q", str(project.root)], check=True)
    assert "<exit 0>" not in _shell(project, "echo x > .git/hooks/pre-commit")


@needs_sandbox
def test_no_project_still_protects_user_paths() -> None:
    from veles.core.user_paths import user_home

    user_home().mkdir(parents=True, exist_ok=True)
    assert "<exit 0>" not in _shell(None, f"echo x > '{user_home()}/trust.json'")


@pytest.mark.skipif(active, reason="the sandbox works here")
def test_without_a_sandbox_run_shell_warns_and_runs(repo: Project, capsys) -> None:
    sandbox._warned.clear()
    assert _shell(repo, "echo x > a.txt").rstrip().endswith("<exit 0>")
    assert "run_shell is not sandboxed" in capsys.readouterr().err
