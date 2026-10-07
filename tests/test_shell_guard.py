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
    """Lock: a name added to the file tools' confirm list is closed for run_shell too.
    `.git` is not a name: existing repos are found and protected, new ones may be made."""
    guard = shell_guard(init_project(tmp_path / "p", name="p"))
    for name in _CONFIRM_NAMES - {".git"}:
        assert name in guard.readonly_names
    assert ".veles" in guard.readonly_names
    assert all("/" not in n and n != ".git" for n in guard.readonly_names)


def _git(*args: str) -> None:
    subprocess.run(["git", *args], check=True, capture_output=True)


def test_a_worktree_protects_the_real_git_config(tmp_path: Path) -> None:
    """`.git` is a file there: the hooks and config git really uses live in the main
    repo, and the file itself must not be repointed."""
    main = tmp_path / "main"
    _git("init", "-q", str(main))
    # CI runners have no git identity.
    _git(
        "-C",
        str(main),
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@t",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "init",
    )
    _git("-C", str(main), "worktree", "add", "-q", str(tmp_path / "wt"), "-b", "side")
    project = init_project(tmp_path / "wt", name="p")
    guard = shell_guard(project)
    real = _real(main) / ".git"
    assert {real / "config", real / "hooks"} <= set(guard.readonly)
    assert _real(tmp_path / "wt") / ".git" in guard.pinned  # the .git file


def test_included_and_global_git_configs_are_closed(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    _git("init", "-q", str(project.root))
    extra = tmp_path / "extra.gitconfig"
    extra.write_text("[user]\n\tname = x\n")
    _git("-C", str(project.root), "config", "include.path", str(extra))
    assert _real(extra) in shell_guard(project).readonly


def test_existing_nested_repos_are_protected_new_ones_are_not(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    nested = project.root / "vendor" / "lib"
    _git("init", "-q", str(nested))
    guard = shell_guard(project)
    git = _real(nested) / ".git"
    assert git in guard.pinned and {git / "hooks", git / "config"} <= set(guard.readonly)
    assert not any(p.name == ".git" for p in guard.pinned if p.parent == _real(project.root))


def test_deep_existing_names_are_found(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    deep = project.root / "a" / "b" / "c" / ".claude"
    deep.mkdir(parents=True)
    assert _real(deep) in shell_guard(project).readonly


def test_home_entries_follow_the_platform(tmp_path: Path) -> None:
    import sys

    readonly = {str(p) for p in shell_guard(None).readonly}
    home = str(_real(Path.home()))
    mac = f"{home}/Library/LaunchAgents" in readonly
    linux = f"{home}/.config/autostart" in readonly
    assert (mac, linux) == ((True, False) if sys.platform == "darwin" else (False, True))


def test_symlinks_on_the_way_to_the_root_are_kept(tmp_path: Path, monkeypatch) -> None:
    """The user entered by `~/code` → `/Volumes/…`: swapping that link for a directory
    would hand them a planted copy of the repo. `$PWD` keeps the path they used."""
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    project = init_project(link / "p", name="p")
    monkeypatch.setenv("PWD", str(link / "p"))
    assert link in shell_guard(project).links


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
