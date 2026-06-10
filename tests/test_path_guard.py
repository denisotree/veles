"""M37 — sandbox enforcement on builtin file/shell tools.

Tests the resolution policy directly + integration with read_file /
write_file / run_shell. We monkey-patch `veles.core.path_guard.Path.home`
and the active-project ContextVar so the sandbox roots point at
`tmp_path` rather than the developer's real `~/.veles/`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.context import reset_active_project, set_active_project
from veles.core.path_guard import (
    SandboxViolation,
    _get_sandbox_roots,
    resolve_safe,
    sandbox_cwd,
)
from veles.core.project import init_project
from veles.core.tools.builtin.read_file import read_file
from veles.core.tools.builtin.run_shell import run_shell
from veles.core.tools.builtin.write_file import write_file


def _set_env_roots(monkeypatch: pytest.MonkeyPatch, *roots: Path) -> None:
    monkeypatch.setenv("VELES_SANDBOX_ROOTS", ":".join(str(r) for r in roots))


@pytest.fixture(autouse=True)
def _clear_leaked_active_project():
    """An earlier test may have left an active project in the ContextVar;
    M39 write_file checks `current_project()`, so clear it for every test
    that doesn't set its own. Tests that need a project still call
    `set_active_project` and reset on tear-down themselves."""
    token = set_active_project(None)
    yield
    reset_active_project(token)


# ---- _get_sandbox_roots ----


def test_env_override_replaces_default_roots(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    a = tmp_path / "a"
    a.mkdir()
    _set_env_roots(monkeypatch, a)
    roots = _get_sandbox_roots()
    assert roots == [a.resolve()]


def test_no_project_falls_back_to_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """When no active project: cwd is in roots; the blanket `~/.veles/`
    root is NOT — only narrow `~/.veles/{skills,locales}` if they exist."""
    monkeypatch.delenv("VELES_SANDBOX_ROOTS", raising=False)
    fake_home = tmp_path / "home_outside"
    fake_home.mkdir()
    monkeypatch.setattr(
        "veles.core.path_guard.Path.home",
        classmethod(lambda cls: fake_home),
    )
    cwd = tmp_path / "cwd_outside"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    token = set_active_project(None)
    try:
        roots = _get_sandbox_roots()
    finally:
        reset_active_project(token)
    assert cwd.resolve() in roots
    assert (fake_home / ".veles").resolve() not in roots


def test_user_root_whitelist_admits_existing_subdirs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`~/.veles/skills` and `~/.veles/locales` are admitted iff they exist;
    `~/.veles/projects` is never admitted regardless of existence.

    Uses `resolve_safe` rather than peeking at `roots` directly so the
    test survives dedupe rearrangement when the fake home happens to sit
    inside the real cwd (pytest temp layout)."""
    monkeypatch.delenv("VELES_SANDBOX_ROOTS", raising=False)
    fake_home = tmp_path / "home"
    skills_root = fake_home / ".veles" / "skills"
    locales_root = fake_home / ".veles" / "locales"
    projects_root = fake_home / ".veles" / "projects"
    for p in (skills_root, locales_root, projects_root):
        p.mkdir(parents=True)
    monkeypatch.setattr(
        "veles.core.path_guard.Path.home",
        classmethod(lambda cls: fake_home),
    )
    # Pin cwd outside fake_home so dedupe doesn't subsume the whitelist roots.
    cwd_outside = tmp_path / "cwd_elsewhere"
    cwd_outside.mkdir()
    monkeypatch.chdir(cwd_outside)
    # Need an active project so `~/.veles/projects/` isn't accidentally
    # admitted via the no-project cwd-fallback branch.
    project = init_project(tmp_path / "p", name="p")
    token = set_active_project(project)
    try:
        # Whitelist hits — both behave as roots.
        sentinel_skill = skills_root / "a.md"
        sentinel_skill.write_text("x", encoding="utf-8")
        sentinel_locale = locales_root / "ru.toml"
        sentinel_locale.write_text("x", encoding="utf-8")
        assert resolve_safe(str(sentinel_skill)) == sentinel_skill.resolve()
        assert resolve_safe(str(sentinel_locale)) == sentinel_locale.resolve()

        # Daemon-internal — rejected.
        sentinel_registry = projects_root / "registry.json"
        sentinel_registry.write_text("{}", encoding="utf-8")
        with pytest.raises(SandboxViolation):
            resolve_safe(str(sentinel_registry))
        with pytest.raises(SandboxViolation):
            resolve_safe(str(fake_home / ".veles" / "config.toml"))
    finally:
        reset_active_project(token)


def test_read_file_rejects_user_root_registry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The Mind Palace leak: agent must not be able to enumerate other
    projects by reading `~/.veles/projects/registry.json`."""
    monkeypatch.delenv("VELES_SANDBOX_ROOTS", raising=False)
    fake_home = tmp_path / "home"
    registry = fake_home / ".veles" / "projects" / "registry.json"
    registry.parent.mkdir(parents=True)
    registry.write_text('{"projects":[]}', encoding="utf-8")
    monkeypatch.setattr(
        "veles.core.path_guard.Path.home",
        classmethod(lambda cls: fake_home),
    )
    project = init_project(tmp_path / "p", name="p")
    token = set_active_project(project)
    try:
        with pytest.raises(SandboxViolation):
            read_file(str(registry))
    finally:
        reset_active_project(token)


def test_read_file_allows_user_root_skills(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Counterpart: a global skill under `~/.veles/skills/` is reachable
    from any project (VISION §8)."""
    monkeypatch.delenv("VELES_SANDBOX_ROOTS", raising=False)
    fake_home = tmp_path / "home"
    skill = fake_home / ".veles" / "skills" / "my-skill" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("# my skill\n", encoding="utf-8")
    monkeypatch.setattr(
        "veles.core.path_guard.Path.home",
        classmethod(lambda cls: fake_home),
    )
    project = init_project(tmp_path / "p", name="p")
    token = set_active_project(project)
    try:
        out = read_file(str(skill))
        assert "my skill" in out
    finally:
        reset_active_project(token)


def test_active_project_replaces_cwd_in_roots(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("VELES_SANDBOX_ROOTS", raising=False)
    monkeypatch.setattr(
        "veles.core.path_guard.Path.home",
        classmethod(lambda cls: tmp_path / "home"),
    )
    project = init_project(tmp_path / "p", name="p")
    token = set_active_project(project)
    try:
        roots = _get_sandbox_roots()
        assert project.root.resolve() in roots
    finally:
        reset_active_project(token)


# ---- resolve_safe ----


def test_resolve_inside_sandbox_returns_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _set_env_roots(monkeypatch, tmp_path)
    target = tmp_path / "subdir" / "file.txt"
    target.parent.mkdir()
    target.write_text("hello", encoding="utf-8")
    assert resolve_safe(str(target)) == target.resolve()


def test_resolve_inside_sandbox_for_nonexistent_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """write_file must work for not-yet-existing paths under the sandbox."""
    _set_env_roots(monkeypatch, tmp_path)
    target = tmp_path / "new" / "file.txt"
    out = resolve_safe(str(target))
    assert out == target.resolve()


def test_resolve_outside_sandbox_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    outside = tmp_path / "outside"
    sandbox.mkdir()
    outside.mkdir()
    _set_env_roots(monkeypatch, sandbox)
    with pytest.raises(SandboxViolation, match="outside sandbox"):
        resolve_safe(str(outside / "x.txt"))


def test_resolve_dotdot_segment_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_env_roots(monkeypatch, tmp_path)
    with pytest.raises(SandboxViolation, match=r"'\.\.'"):
        resolve_safe(str(tmp_path / ".." / "etc"))


def test_resolve_symlink_pointing_outside_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sandbox = tmp_path / "sandbox"
    outside = tmp_path / "outside"
    sandbox.mkdir()
    outside.mkdir()
    target = outside / "secret.txt"
    target.write_text("classified", encoding="utf-8")
    link = sandbox / "shortcut"
    link.symlink_to(target)
    _set_env_roots(monkeypatch, sandbox)
    with pytest.raises(SandboxViolation, match="outside sandbox"):
        resolve_safe(str(link))


def test_resolve_symlink_inside_sandbox_ok(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    real = sandbox / "real.txt"
    real.write_text("ok", encoding="utf-8")
    link = sandbox / "link.txt"
    link.symlink_to(real)
    _set_env_roots(monkeypatch, sandbox)
    out = resolve_safe(str(link))
    assert out == real.resolve()


def test_resolve_with_multiple_roots_picks_first_match(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    _set_env_roots(monkeypatch, a, b)
    target = b / "file.txt"
    out = resolve_safe(str(target))
    assert out == target.resolve()


# ---- builtin tool integration ----


def test_read_file_inside_sandbox_works(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_env_roots(monkeypatch, tmp_path)
    target = tmp_path / "f.txt"
    target.write_text("line1\nline2\n", encoding="utf-8")
    out = read_file(str(target))
    assert "line1" in out and "line2" in out


def test_read_file_outside_sandbox_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    outside = tmp_path / "outside"
    sandbox.mkdir()
    outside.mkdir()
    target = outside / "f.txt"
    target.write_text("oops", encoding="utf-8")
    _set_env_roots(monkeypatch, sandbox)
    with pytest.raises(SandboxViolation):
        read_file(str(target))


def test_write_file_inside_sandbox_works(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_env_roots(monkeypatch, tmp_path)
    target = tmp_path / "out.txt"
    msg = write_file(str(target), "hello world")
    assert "wrote" in msg
    assert target.read_text(encoding="utf-8") == "hello world"


def test_write_file_outside_sandbox_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    _set_env_roots(monkeypatch, sandbox)
    with pytest.raises(SandboxViolation):
        write_file(str(tmp_path / "outside.txt"), "x")


def test_run_shell_uses_sandbox_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_env_roots(monkeypatch, tmp_path)
    out = run_shell("pwd")
    assert str(tmp_path.resolve()) in out


def test_sandbox_cwd_returns_first_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    _set_env_roots(monkeypatch, a, b)
    assert sandbox_cwd() == a.resolve()
