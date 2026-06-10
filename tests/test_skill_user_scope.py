"""M40 — user-scope skill discovery, install, promote, demote."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.project import init_project
from veles.core.skill_install import (
    SkillInstallError,
    SkillNotFoundError,
    demote_skill,
    install_skill_from_source,
    promote_skill,
    remove_skill,
)
from veles.core.skills import discover_skills, parse_frontmatter, user_skills_dir

# ---------- harness ----------


# `isolated_user_home` comes from tests/conftest.py and yields the
# `<home>/.veles/` directory itself.


def _write_skill(parent: Path, name: str, *, description: str, body: str = "body") -> Path:
    skill_dir = parent / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n{body}\n",
        encoding="utf-8",
    )
    return skill_dir


def _write_skill_with_telemetry(
    parent: Path, name: str, *, description: str, use: int, success: int, errors: int
) -> Path:
    skill_dir = parent / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n"
        f"use_count: {use}\nsuccess_count: {success}\n"
        f"error_count: {errors}\nlast_used: 2026-05-01T00:00:00Z\n"
        f"last_error_at: 2026-05-02T00:00:00Z\n---\nbody\n",
        encoding="utf-8",
    )
    return skill_dir


# ---------- user_skills_dir ----------


def test_user_skills_dir_uses_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path))
    assert user_skills_dir() == tmp_path / ".veles" / "skills"


def test_user_skills_dir_falls_back_to_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("VELES_USER_HOME", raising=False)
    monkeypatch.setattr("veles.core.skills.Path.home", classmethod(lambda cls: tmp_path))
    assert user_skills_dir() == tmp_path / ".veles" / "skills"


# ---------- discover merge ----------


def test_discover_returns_user_skills_when_no_project_skills(
    isolated_user_home: Path, tmp_path: Path
) -> None:
    _write_skill(isolated_user_home / "skills", "u1", description="user one")
    project = init_project(tmp_path / "proj", name="proj")
    skills = discover_skills(project)
    assert [(s.name, s.scope) for s in skills] == [("u1", "user")]


def test_discover_returns_project_first_then_user(isolated_user_home: Path, tmp_path: Path) -> None:
    _write_skill(isolated_user_home / "skills", "user-only", description="u")
    project = init_project(tmp_path / "proj", name="proj")
    _write_skill(project.skills_dir, "proj-only", description="p")
    skills = discover_skills(project)
    names_scopes = [(s.name, s.scope) for s in skills]
    assert names_scopes == [("proj-only", "project"), ("user-only", "user")]


def test_discover_project_overrides_user_on_collision(
    isolated_user_home: Path, tmp_path: Path
) -> None:
    _write_skill(isolated_user_home / "skills", "shared", description="user version")
    project = init_project(tmp_path / "proj", name="proj")
    _write_skill(project.skills_dir, "shared", description="project version")
    skills = discover_skills(project)
    shared = [s for s in skills if s.name == "shared"]
    assert len(shared) == 1
    assert shared[0].scope == "project"
    assert shared[0].description == "project version"


def test_discover_handles_missing_user_dir(isolated_user_home: Path, tmp_path: Path) -> None:
    """When ~/.veles/skills doesn't exist, discovery still returns project skills."""
    project = init_project(tmp_path / "proj", name="proj")
    _write_skill(project.skills_dir, "p1", description="d")
    skills = discover_skills(project)
    assert [s.name for s in skills] == ["p1"]
    assert skills[0].scope == "project"


# ---------- install scope ----------


def test_install_user_scope_writes_to_user_dir(isolated_user_home: Path, tmp_path: Path) -> None:
    src = tmp_path / "src"
    _write_skill(src, "u-skill", description="user-installed")
    project = init_project(tmp_path / "proj", name="proj")
    skill = install_skill_from_source(str(src / "u-skill"), project=project, scope="user")
    assert skill.scope == "user"
    assert skill.path.parent == isolated_user_home / "skills" / "u-skill"


def test_install_project_scope_unchanged(isolated_user_home: Path, tmp_path: Path) -> None:
    src = tmp_path / "src"
    _write_skill(src, "p-skill", description="d")
    project = init_project(tmp_path / "proj", name="proj")
    skill = install_skill_from_source(str(src / "p-skill"), project=project)
    assert skill.scope == "project"
    assert skill.path.parent == project.skills_dir / "p-skill"


def test_install_unknown_scope_raises(isolated_user_home: Path, tmp_path: Path) -> None:
    src = tmp_path / "src"
    _write_skill(src, "x", description="d")
    project = init_project(tmp_path / "proj", name="proj")
    with pytest.raises(SkillInstallError, match="unknown scope"):
        install_skill_from_source(str(src / "x"), project=project, scope="garbage")


# ---------- remove scope ----------


def test_remove_user_scope_deletes_from_user_dir(isolated_user_home: Path, tmp_path: Path) -> None:
    user_dir = isolated_user_home / "skills"
    _write_skill(user_dir, "drop", description="d")
    project = init_project(tmp_path / "proj", name="proj")
    remove_skill("drop", project=project, scope="user")
    assert not (user_dir / "drop").exists()


def test_remove_user_scope_missing_raises(isolated_user_home: Path, tmp_path: Path) -> None:
    project = init_project(tmp_path / "proj", name="proj")
    with pytest.raises(SkillNotFoundError, match="user-scope"):
        remove_skill("nope", project=project, scope="user")


# ---------- promote ----------


def test_promote_copies_project_to_user(isolated_user_home: Path, tmp_path: Path) -> None:
    project = init_project(tmp_path / "proj", name="proj")
    _write_skill(project.skills_dir, "to-promote", description="d")
    dst = promote_skill("to-promote", project=project)
    assert dst == isolated_user_home / "skills" / "to-promote"
    assert (dst / "SKILL.md").is_file()
    # Source still exists (promote = copy, not move).
    assert (project.skills_dir / "to-promote" / "SKILL.md").is_file()


def test_promote_resets_telemetry_by_default(isolated_user_home: Path, tmp_path: Path) -> None:
    project = init_project(tmp_path / "proj", name="proj")
    _write_skill_with_telemetry(
        project.skills_dir, "stats", description="d", use=42, success=30, errors=12
    )
    dst = promote_skill("stats", project=project)
    fm, _ = parse_frontmatter((dst / "SKILL.md").read_text(encoding="utf-8"))
    assert fm["use_count"] == 0
    assert fm["success_count"] == 0
    assert fm["error_count"] == 0
    assert fm["last_used"] is None
    assert fm["last_error_at"] is None


def test_promote_keeps_telemetry_when_requested(isolated_user_home: Path, tmp_path: Path) -> None:
    project = init_project(tmp_path / "proj", name="proj")
    _write_skill_with_telemetry(
        project.skills_dir, "stats", description="d", use=42, success=30, errors=12
    )
    dst = promote_skill("stats", project=project, reset_telemetry=False)
    fm, _ = parse_frontmatter((dst / "SKILL.md").read_text(encoding="utf-8"))
    assert fm["use_count"] == 42
    assert fm["success_count"] == 30
    assert fm["error_count"] == 12


def test_promote_refuses_on_user_collision(isolated_user_home: Path, tmp_path: Path) -> None:
    project = init_project(tmp_path / "proj", name="proj")
    _write_skill(project.skills_dir, "dup", description="proj")
    _write_skill(isolated_user_home / "skills", "dup", description="user")
    with pytest.raises(SkillInstallError, match="already exists"):
        promote_skill("dup", project=project)


def test_promote_refuses_when_project_skill_missing(
    isolated_user_home: Path, tmp_path: Path
) -> None:
    project = init_project(tmp_path / "proj", name="proj")
    with pytest.raises(SkillNotFoundError, match="project-scope"):
        promote_skill("ghost", project=project)


# ---------- demote ----------


def test_demote_copies_user_to_project(isolated_user_home: Path, tmp_path: Path) -> None:
    project = init_project(tmp_path / "proj", name="proj")
    _write_skill(isolated_user_home / "skills", "to-demote", description="d")
    dst = demote_skill("to-demote", project=project)
    assert dst == project.skills_dir / "to-demote"
    assert (dst / "SKILL.md").is_file()


def test_demote_preserves_telemetry(isolated_user_home: Path, tmp_path: Path) -> None:
    project = init_project(tmp_path / "proj", name="proj")
    _write_skill_with_telemetry(
        isolated_user_home / "skills",
        "stats",
        description="d",
        use=15,
        success=10,
        errors=5,
    )
    dst = demote_skill("stats", project=project)
    fm, _ = parse_frontmatter((dst / "SKILL.md").read_text(encoding="utf-8"))
    assert fm["use_count"] == 15
    assert fm["success_count"] == 10
    assert fm["error_count"] == 5


def test_demote_refuses_on_project_collision(isolated_user_home: Path, tmp_path: Path) -> None:
    project = init_project(tmp_path / "proj", name="proj")
    _write_skill(isolated_user_home / "skills", "dup", description="user")
    _write_skill(project.skills_dir, "dup", description="proj")
    with pytest.raises(SkillInstallError, match="already exists"):
        demote_skill("dup", project=project)


def test_demote_refuses_when_user_skill_missing(isolated_user_home: Path, tmp_path: Path) -> None:
    project = init_project(tmp_path / "proj", name="proj")
    with pytest.raises(SkillNotFoundError, match="user-scope"):
        demote_skill("ghost", project=project)
