"""Release F: the sandbox profile / argv built from a ShellGuard, the once-per-process
probe, and the notes appended to run_shell's output. Pure: no sandbox needed."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from veles.core import sandbox
from veles.core.layout.writable import ShellGuard


def _guard(root: Path) -> ShellGuard:
    state = root / ".veles"
    return ShellGuard(
        root=root,
        readonly=(root / ".git" / "hooks", state, Path("/u/home/.zshrc")),
        readonly_names=(".envrc", ".git/hooks"),
        holes=(state / "tmp",),
        relock_prefix=state / "tmp" / "delegate-",
        pinned=(root, root / ".git"),
        links=(),
    )


@pytest.fixture(autouse=True)
def _fresh() -> None:
    sandbox._probe.cache_clear()
    sandbox._warned.clear()


def test_profile_denies_then_reopens_holes_then_relocks() -> None:
    prof = sandbox.sbpl_profile(_guard(Path("/w/proj")))
    deny, allow, relock = (
        prof.index(s) for s in ("(deny file-write*", "(allow file-write*", "delegate-")
    )
    assert deny < allow < relock
    assert '(subpath "/w/proj/.git/hooks")' in prof
    assert '(subpath "/w/proj/.veles/tmp")' in prof
    for literal in ("/w/proj", "/w/proj/.git"):
        assert f'(literal "{literal}")' in prof  # pinned (existing ancestors: own test)
    assert '(literal "/")' not in prof


def test_names_match_any_case() -> None:
    prof = sandbox.sbpl_profile(_guard(Path("/w/proj")))
    # SBPL string form: the regex's backslashes are doubled.
    assert r"\\.[eE][nN][vV][rR][cC](/|$)" in prof
    assert r"\\.[gG][iI][tT]/[hH][oO][oO][kK][sS](/|$)" in prof


def test_profile_escapes_odd_root_names() -> None:
    prof = sandbox.sbpl_profile(_guard(Path('/w/my "odd" proj')))
    assert '(subpath "/w/my \\"odd\\" proj/.git/hooks")' in prof
    assert r'(regex "^/w/my \"odd\" proj/(.*/)?' in prof
    assert '#"' not in prof  # the raw-regex literal can't hold a quote


def test_profile_uses_canonical_paths(tmp_path: Path) -> None:
    from veles.core.layout.writable import shell_guard
    from veles.core.project import init_project

    real = tmp_path / "real"
    (real / "proj").mkdir(parents=True)
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    prof = sandbox.sbpl_profile(shell_guard(init_project(link / "proj", name="p")))
    assert str(link) not in prof


def test_bwrap_order_pins_then_readonly_then_holes_then_relock(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    (root / ".veles" / "tmp" / "delegate-1").mkdir(parents=True)
    (root / "sub").mkdir()
    (root / "sub" / ".envrc").write_text("x")
    argv = sandbox.bwrap_argv(_guard(root), ["bash", "-c", "true"])
    flat = " ".join(argv)
    assert argv[:4] == ["bwrap", "--dev-bind", "/", "/"]
    assert argv[-4:] == ["--", "bash", "-c", "true"] and "--die-with-parent" in argv
    assert flat.index(f"--bind-try {root} {root}") < flat.index(f"--ro-bind-try {root}/.veles ")
    assert flat.index(f"--ro-bind-try {root}/.veles ") < flat.index(
        f"--bind-try {root}/.veles/tmp "
    )
    assert flat.index(f"--bind-try {root}/.veles/tmp ") < flat.index("delegate-1")


def test_missing_ancestors_are_not_literal_denied(tmp_path: Path) -> None:
    """A literal deny on a missing dir blocks creating it (`~/.config` absent broke gh);
    only an existing ancestor can be renamed away."""
    guard = ShellGuard(
        root=None,
        readonly=(tmp_path / "home" / ".config" / "fish",),
        readonly_names=(),
        holes=(),
        relock_prefix=None,
        pinned=(),
        links=(),
    )
    (tmp_path / "home").mkdir()
    prof = sandbox.sbpl_profile(guard)
    assert f'(literal "{tmp_path / "home"}")' in prof
    assert f'(literal "{tmp_path / "home" / ".config"}")' not in prof


def test_bwrap_skips_paths_under_a_file_and_seals_a_git_file(tmp_path: Path) -> None:
    """In a worktree `.git` is a file: `--ro-bind-try .git/hooks` failed with ENOTDIR and
    every run_shell broke; the file itself must be read-only, not bound read-write."""
    root = tmp_path / "wt"
    root.mkdir()
    (root / ".git").write_text("gitdir: /elsewhere\n")
    guard = ShellGuard(
        root=root,
        readonly=(root / ".git" / "hooks",),
        readonly_names=(),
        holes=(),
        relock_prefix=None,
        pinned=(root, root / ".git"),
        links=(),
    )
    flat = " ".join(sandbox.bwrap_argv(guard, ["true"]))
    assert f"{root}/.git/hooks" not in flat
    assert f"--ro-bind-try {root}/.git {root}/.git" in flat
    assert f"--bind-try {root} {root}" in flat


def test_links_are_literal_denied() -> None:
    guard = ShellGuard(
        root=None,
        readonly=(),
        readonly_names=(),
        holes=(),
        relock_prefix=None,
        pinned=(),
        links=(Path("/u/code"),),
    )
    assert '(literal "/u/code")' in sandbox.sbpl_profile(guard)


def test_a_busy_mount_gets_the_hint() -> None:
    """On Linux git's rename onto the read-only `.git/config` mount fails with EBUSY."""
    w = sandbox.Wrapped(["x"], True)
    out = "error: could not commit config file .git/config: Device or resource busy"
    assert "read-only for the agent's shell" in sandbox.notes(
        w, returncode=255, output=out, project=None
    )


def test_a_sandbox_that_fails_to_start_is_reported(capsys) -> None:
    w = sandbox.Wrapped(["x"], True)
    out = "bwrap: Can't find source path /p/.git/hooks: Not a directory\n"
    note = sandbox.notes(w, returncode=1, output=out, project=None)
    assert "didn't run" in note
    assert "sandbox failed to start" in capsys.readouterr().err


def test_watch_covers_a_new_repo_and_on_linux_new_home_entries(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    guard = ShellGuard(
        root=root,
        readonly=(home / ".bash_profile",),
        readonly_names=(".envrc",),
        holes=(),
        relock_prefix=None,
        pinned=(root,),
        links=(),
    )
    assert set(sandbox._watch(guard, linux=False)) == {root / ".git"}
    assert set(sandbox._watch(guard, linux=True)) == {
        root / ".git",
        root / ".envrc",
        home / ".bash_profile",
    }


def test_bwrap_creates_missing_holes_first(tmp_path: Path, monkeypatch) -> None:
    """bwrap can't bind a path that doesn't exist: with `.veles/` read-only, a fresh
    project's `.veles/tmp` could never be created (Linux CI)."""
    from veles.core.project import init_project

    project = init_project(tmp_path / "p", name="p")
    monkeypatch.setattr(sandbox, "sandbox_status", lambda: sandbox.SandboxStatus("bwrap", True))
    assert not (project.state_dir / "tmp").exists()
    sandbox.wrap(["true"], project)
    assert (project.state_dir / "tmp").is_dir() and (project.state_dir / "artifacts").is_dir()


def test_disabled_runs_plain_and_quietly(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sandbox, "_enabled", lambda: False)
    wrapped = sandbox.wrap(["bash", "-c", "true"], None)
    assert wrapped.argv == ["bash", "-c", "true"] and not wrapped.active
    assert sandbox.sandbox_status().disabled
    assert capsys.readouterr().err == ""


def test_unavailable_warns_once(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sandbox, "_enabled", lambda: True)
    monkeypatch.setattr(sandbox.shutil, "which", lambda _n: None)
    for _ in range(2):
        assert not sandbox.wrap(["true"], None).active
    assert capsys.readouterr().err.count("run_shell is not sandboxed") == 1


def test_a_failing_probe_is_unavailable_with_its_reason(monkeypatch) -> None:
    monkeypatch.setattr(sandbox, "_enabled", lambda: True)
    monkeypatch.setattr(sandbox.shutil, "which", lambda n: f"/usr/bin/{n}")
    monkeypatch.setattr(
        sandbox.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(
            a[0], 1, "", "bwrap: No permissions to create a new namespace\n"
        ),
    )
    status = sandbox.sandbox_status()
    assert not status.active and "No permissions" in status.reason


def test_denied_write_gets_the_hint() -> None:
    w = sandbox.Wrapped(["x"], True)
    note = sandbox.notes(
        w, returncode=1, output="bash: .git/config: Operation not permitted", project=None
    )
    assert "read-only for the agent's shell" in note
    assert sandbox.notes(w, returncode=0, output="Operation not permitted", project=None) == ""


def test_a_created_protected_file_is_reported(tmp_path: Path, capsys) -> None:
    from veles.core.memory.artefacts import memory_log_path
    from veles.core.project import init_project

    project = init_project(tmp_path / "p", name="p")
    envrc = project.root / ".envrc"
    w = sandbox.Wrapped(["x"], True, watch=(envrc,))
    envrc.write_text("export X=1")
    note = sandbox.notes(w, returncode=0, output="", project=project)
    assert ".envrc" in note and ".envrc" in capsys.readouterr().err
    assert ".envrc" in memory_log_path(project).read_text(encoding="utf-8")
