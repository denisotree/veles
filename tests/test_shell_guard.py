"""Release F: what the agent's run_shell may not write — the file-tool rules plus the
user's own auto-run files, as canonical paths."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from veles.core.layout.writable import _CONFIRM_NAMES, AGENT_WRITABLE_STATE, shell_guard
from veles.core.project import init_project
from veles.core.user_paths import user_home


def _real(p: Path) -> Path:
    return Path(os.path.realpath(p))


def test_every_file_tool_name_is_closed_for_the_shell(tmp_path: Path) -> None:
    """Lock: a name added to the file tools' confirm list is closed for run_shell too."""
    guard = shell_guard(init_project(tmp_path / "p", name="p"))
    for name in _CONFIRM_NAMES - {".git"}:
        assert name in guard.readonly_names
    assert ".veles" in guard.readonly_names
    assert {".git/hooks", ".git/config", ".git/config.worktree"} <= set(guard.readonly_names)


def test_git_code_paths_not_the_whole_git_dir(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    subprocess.run(["git", "init", "-q", str(project.root)], check=True)
    guard = shell_guard(project)
    git = _real(project.root) / ".git"
    assert {git / "hooks", git / "config"} <= set(guard.readonly)
    assert git not in guard.readonly
    assert guard.pinned == (_real(project.root), git)


def test_veles_state_is_closed_with_the_agent_dirs_open(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    guard = shell_guard(project)
    state = _real(project.state_dir)
    assert state in guard.readonly
    assert {state / n for n in AGENT_WRITABLE_STATE} == set(guard.holes)
    assert guard.relock_prefix == state / "tmp" / "delegate-"


def test_user_paths_are_closed() -> None:
    guard = shell_guard(None)
    home = Path.home()
    assert _real(user_home()) in guard.readonly
    for rel in (".zshrc", ".bashrc", ".ssh", ".gitconfig", ".claude", ".codex", ".gemini"):
        assert _real(home / rel) in guard.readonly
    assert guard.root is None and guard.readonly_names == () and guard.pinned == ()


def test_custom_hooks_path_is_closed(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    subprocess.run(["git", "init", "-q", str(project.root)], check=True)
    subprocess.run(
        ["git", "-C", str(project.root), "config", "core.hooksPath", "tools/hooks"], check=True
    )
    assert _real(project.root / "tools" / "hooks") in shell_guard(project).readonly


def test_paths_are_canonical(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    project = init_project(link / "p", name="p")
    guard = shell_guard(project)
    assert guard.root == _real(real / "p")
    assert all(str(p).startswith(str(_real(real))) for p in guard.holes)
