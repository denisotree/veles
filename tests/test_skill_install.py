"""Unit tests for skill install/remove flow.

Avoids real network: git clone is monkey-patched to copy a fixture
directory. Local-path installs use real shutil.copytree.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from veles.core.project import init_project
from veles.core.skill_install import (
    SkillInstallError,
    SkillNotFoundError,
    _derive_name,
    _is_git_url,
    install_skill_from_source,
    remove_skill,
)


def _make_skill_fixture(
    root: Path, *, name: str = "greet", description: str = "Greet user"
) -> Path:
    skill_dir = root / f"fixture-{name}"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\nBody.\n",
        encoding="utf-8",
    )
    return skill_dir


# ---------- helpers ----------


def test_is_git_url_recognises_common_schemes() -> None:
    assert _is_git_url("https://github.com/u/r.git")
    assert _is_git_url("git@github.com:u/r.git")
    assert _is_git_url("ssh://git@host/u/r")
    assert _is_git_url("git://host/u/r.git")
    assert _is_git_url("https://gitlab.com/u/r")
    assert not _is_git_url("/local/path")
    assert not _is_git_url("./local")
    assert not _is_git_url("just-a-name")


def test_derive_name_strips_dot_git_suffix() -> None:
    assert _derive_name("https://github.com/user/foo-skill.git") == "foo-skill"
    assert _derive_name("git@github.com:user/Bar_Baz.git") == "bar-baz"


def test_derive_name_for_local_path(tmp_path: Path) -> None:
    src = tmp_path / "my-skill-dir"
    src.mkdir()
    assert _derive_name(str(src)) == "my-skill-dir"


# ---------- install ----------


def test_install_from_local_directory_succeeds(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    src = _make_skill_fixture(tmp_path / "src", name="greet")
    skill = install_skill_from_source(str(src), project=project, name_override="greet")
    assert skill.name == "greet"
    assert (project.skills_dir / "greet" / "SKILL.md").is_file()


def test_install_with_name_override(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    src = _make_skill_fixture(tmp_path / "src", name="greet")
    skill = install_skill_from_source(str(src), project=project, name_override="greet")
    assert skill.name == "greet"


def test_install_rejects_existing_non_empty_target(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    src = _make_skill_fixture(tmp_path / "src", name="greet")
    install_skill_from_source(str(src), project=project, name_override="greet")
    # Install again — must fail without overwriting.
    with pytest.raises(SkillInstallError, match="already exists"):
        install_skill_from_source(str(src), project=project, name_override="greet")


def test_install_cleans_up_when_skill_md_missing(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    src = tmp_path / "bad-src"
    src.mkdir()
    (src / "README.md").write_text("not a skill", encoding="utf-8")
    with pytest.raises(SkillInstallError, match=r"no SKILL\.md"):
        install_skill_from_source(str(src), project=project, name_override="bad")
    assert not (project.skills_dir / "bad").exists()


def test_install_cleans_up_when_frontmatter_invalid(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    src = tmp_path / "invalid-src"
    src.mkdir()
    # SKILL.md with no frontmatter at all → discover_skills skips it.
    (src / "SKILL.md").write_text("just body, no frontmatter", encoding="utf-8")
    with pytest.raises(SkillInstallError, match="discover_skills"):
        install_skill_from_source(str(src), project=project, name_override="invalid")
    assert not (project.skills_dir / "invalid").exists()


def test_install_rejects_unknown_source_format(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    with pytest.raises(SkillInstallError, match="neither a git URL nor a directory"):
        install_skill_from_source("nonexistent-thing-xyz", project=project)


def test_install_from_git_invokes_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = init_project(tmp_path / "p", name="p")
    fixture = _make_skill_fixture(tmp_path / "src", name="cloned")
    captured: dict = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        captured["env"] = kw.get("env")
        # Simulate `git clone <url> <target>` by copying the fixture into target.
        target = Path(cmd[-1])
        shutil.copytree(fixture, target)
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr("veles.core.skill_install.subprocess.run", fake_run)
    skill = install_skill_from_source(
        "https://github.com/user/cloned.git", project=project, name_override="cloned"
    )
    assert skill.name == "cloned"
    assert captured["cmd"][:3] == ["git", "clone", "--depth"]
    assert captured["env"]["GIT_TERMINAL_PROMPT"] == "0"


def test_install_from_git_propagates_clone_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = init_project(tmp_path / "p", name="p")

    def fake_run(cmd, **kw):
        raise subprocess.CalledProcessError(
            128, cmd, output=b"", stderr=b"fatal: Repository not found"
        )

    monkeypatch.setattr("veles.core.skill_install.subprocess.run", fake_run)
    with pytest.raises(SkillInstallError, match="Repository not found"):
        install_skill_from_source(
            "https://github.com/user/missing.git", project=project, name_override="missing"
        )
    assert not (project.skills_dir / "missing").exists()


# ---------- remove ----------


def test_remove_existing_skill_deletes_directory(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    src = _make_skill_fixture(tmp_path / "src", name="greet")
    install_skill_from_source(str(src), project=project, name_override="greet")
    assert (project.skills_dir / "greet").is_dir()
    remove_skill("greet", project=project)
    assert not (project.skills_dir / "greet").exists()


def test_remove_nonexistent_skill_raises(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    with pytest.raises(SkillNotFoundError):
        remove_skill("ghost", project=project)
