"""M120b: builtin Veles skills (tool_authoring, tool_installer) mount
alongside the layout-pack via discover_skills(include_layout=True)."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.project import init_project
from veles.core.skills import (
    discover_skills,
    mount_builtin_skills,
)


@pytest.fixture()
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


# ---- mount_builtin_skills ----


def test_builtin_skills_discovered() -> None:
    skills = mount_builtin_skills()
    names = {s.name for s in skills}
    assert {"tool_authoring", "tool_installer", "structure_design"} <= names


def test_structure_design_skill_scaffolds_via_wiki_add_category() -> None:
    """The structure_design skill designs a wiki structure from the user's
    description and scaffolds it — its tool budget must include the runtime
    category-declaration tool, and its body must NOT bake in a fixed schema."""
    by_name = {s.name: s for s in mount_builtin_skills()}
    skill = by_name["structure_design"]
    assert "wiki_add_category" in skill.tools and "make_dir" in skill.tools
    assert {"data_type"} <= {p["name"] for p in skill.parameters}
    # Derives schema from the description; diary/tasks/projects are examples only.
    assert "hardcode" in skill.body.lower() and "{data_type}" in skill.body


def test_builtin_skills_have_builtin_scope() -> None:
    for s in mount_builtin_skills():
        assert s.scope == "builtin"


def test_builtin_tool_authoring_declares_write_file() -> None:
    by_name = {s.name: s for s in mount_builtin_skills()}
    skill = by_name["tool_authoring"]
    assert "write_file" in skill.tools


def test_builtin_tool_installer_declares_read_file() -> None:
    by_name = {s.name: s for s in mount_builtin_skills()}
    skill = by_name["tool_installer"]
    assert "read_file" in skill.tools


def test_builtin_tool_skills_declare_advisor_review() -> None:
    """M120c: both tool skills run an advisor code-review before finalising,
    so `advisor_review` must be in their declared tool surface and the review
    step must be in the body."""
    by_name = {s.name: s for s in mount_builtin_skills()}
    for name in ("tool_authoring", "tool_installer"):
        skill = by_name[name]
        assert "advisor_review" in skill.tools, name
        assert "advisor_review" in skill.body, name


def test_builtin_skills_parameters_present() -> None:
    """tool_authoring takes a (tool_name, task_description); installer
    takes (source_path, tool_name). Each skill declares params so
    `make_skill_tool` builds the right schema."""
    by_name = {s.name: s for s in mount_builtin_skills()}
    auth_params = {p["name"] for p in by_name["tool_authoring"].parameters}
    assert {"tool_name", "task_description"} <= auth_params
    inst_params = {p["name"] for p in by_name["tool_installer"].parameters}
    assert {"source_path", "tool_name"} <= inst_params


# ---- discover_skills integration ----


def test_builtin_skills_show_up_via_discover_include_layout(
    isolated_home: Path, tmp_path: Path
) -> None:
    project = init_project(tmp_path / "proj", name="proj")
    skills = discover_skills(project, include_layout=True)
    names = {s.name for s in skills}
    assert {"tool_authoring", "tool_installer"} <= names


def test_builtin_skills_omitted_without_include_layout(isolated_home: Path, tmp_path: Path) -> None:
    """Default discover_skills() doesn't include builtin skills —
    they only appear when callers explicitly opt in. Legacy tests
    that pre-date M120b still see an empty list on a fresh project."""
    project = init_project(tmp_path / "proj", name="proj")
    skills = discover_skills(project)
    names = {s.name for s in skills}
    assert "tool_authoring" not in names
    assert "tool_installer" not in names


def test_project_skill_shadows_builtin(isolated_home: Path, tmp_path: Path) -> None:
    """A project-level `tool_authoring/SKILL.md` overrides the builtin."""
    project = init_project(tmp_path / "proj", name="proj")
    custom = project.skills_dir / "tool_authoring"
    custom.mkdir(parents=True, exist_ok=True)
    (custom / "SKILL.md").write_text(
        "---\nname: tool_authoring\ndescription: project-local override\n---\nbody\n",
        encoding="utf-8",
    )
    skills = discover_skills(project, include_layout=True)
    by_name = {s.name: s for s in skills}
    assert by_name["tool_authoring"].scope == "project"
    assert by_name["tool_authoring"].description == "project-local override"
