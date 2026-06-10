"""M117b: layout-pack skills mount into discover_skills.

A project's active layout-pack contributes its `skills/<name>/SKILL.md`
files to the discover list, at builtin priority (overridden by project
and user level). Default `llm-wiki` pack ships `ingest`, `query`, `lint`
— after M117b they're agent-callable without any wiring.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.project import init_project, load_project
from veles.core.skills import discover_skills, mount_layout_skills


@pytest.fixture()
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


def _write_skill(skills_dir: Path, name: str, body: str, *, description: str = "") -> None:
    sd = skills_dir / name
    sd.mkdir(parents=True, exist_ok=True)
    fm = f"---\nname: {name}\ndescription: {description or f'skill {name}'}\n---\n{body}\n"
    (sd / "SKILL.md").write_text(fm, encoding="utf-8")


# ---- mount_layout_skills directly ----


def test_default_layout_skills_discovered(isolated_home: Path, tmp_path: Path) -> None:
    """A fresh project on the builtin `llm-wiki` pack sees ingest /
    query / lint skills via mount_layout_skills."""
    project = init_project(tmp_path / "proj", name="proj")
    skills = mount_layout_skills(project)
    names = {s.name for s in skills}
    assert {"ingest", "query", "lint"} <= names


def test_pack_skills_have_builtin_scope(isolated_home: Path, tmp_path: Path) -> None:
    project = init_project(tmp_path / "proj", name="proj")
    skills = mount_layout_skills(project)
    for s in skills:
        assert s.scope == "builtin"


def test_pack_skill_has_expected_tools(
    isolated_home: Path, tmp_path: Path
) -> None:
    """The `ingest` skill in llm-wiki declares fetch_url / read_file /
    wiki_write_page / wiki_append_log per its frontmatter."""
    project = init_project(tmp_path / "proj", name="proj")
    skills = mount_layout_skills(project)
    by_name = {s.name: s for s in skills}
    ingest = by_name["ingest"]
    assert "wiki_write_page" in ingest.tools


def test_unknown_layout_returns_empty(
    isolated_home: Path, tmp_path: Path
) -> None:
    """If the project points at a layout that doesn't exist, we don't
    crash — we return an empty list and let the agent run with just
    project + user skills."""
    project = init_project(tmp_path / "proj", name="proj")
    # Mutate project.toml to reference a non-existent pack
    toml_path = project.project_toml_path
    text = toml_path.read_text(encoding="utf-8")
    toml_path.write_text(
        text.replace('layout = "llm-wiki"', 'layout = "ghost-pack"'),
        encoding="utf-8",
    )
    reloaded = load_project(project.root)
    assert reloaded.layout_name == "ghost-pack"
    assert mount_layout_skills(reloaded) == []


# ---- discover_skills integration ----


def test_discover_skills_includes_layout_pack(
    isolated_home: Path, tmp_path: Path
) -> None:
    project = init_project(tmp_path / "proj", name="proj")
    skills = discover_skills(project, include_layout=True)
    names = {s.name for s in skills}
    assert {"ingest", "query", "lint"} <= names


def test_project_skill_shadows_pack_skill(
    isolated_home: Path, tmp_path: Path
) -> None:
    """If a project ships its own `ingest` SKILL.md, it overrides the
    layout-pack version. The override invariant: project > user > pack."""
    project = init_project(tmp_path / "proj", name="proj")
    _write_skill(
        project.skills_dir,
        "ingest",
        "project-local ingest body",
        description="project ingest override",
    )
    skills = discover_skills(project, include_layout=True)
    by_name = {s.name: s for s in skills}
    # Project version wins
    assert by_name["ingest"].scope == "project"
    assert "project-local ingest body" in by_name["ingest"].body


def test_user_skill_shadows_pack_skill(
    isolated_home: Path, tmp_path: Path
) -> None:
    project = init_project(tmp_path / "proj", name="proj")
    user_skills = isolated_home / ".veles" / "skills"
    _write_skill(
        user_skills, "query", "user-level query body", description="user query"
    )
    skills = discover_skills(project, include_layout=True)
    by_name = {s.name: s for s in skills}
    # User version wins over pack version
    assert by_name["query"].scope == "user"
    assert "user-level query body" in by_name["query"].body


def test_project_shadows_user_shadows_pack(
    isolated_home: Path, tmp_path: Path
) -> None:
    """Full three-way override: project > user > pack on the same name."""
    project = init_project(tmp_path / "proj", name="proj")
    user_skills = isolated_home / ".veles" / "skills"
    _write_skill(
        user_skills, "lint", "user lint body", description="user lint"
    )
    _write_skill(
        project.skills_dir, "lint", "project lint body", description="project lint"
    )
    skills = discover_skills(project, include_layout=True)
    by_name = {s.name: s for s in skills}
    assert by_name["lint"].scope == "project"


def test_pack_skill_with_extends_field_loaded(
    isolated_home: Path, tmp_path: Path
) -> None:
    """The layout-pack SKILL.md goes through the same parser, so any
    `extends:` field set in pack frontmatter is honoured. (None of the
    shipped llm-wiki skills use it, but the loader path must remain
    uniform across scopes.)"""
    project = init_project(tmp_path / "proj", name="proj")
    skills = mount_layout_skills(project)
    # All shipped llm-wiki skills don't use extends — they're standalone.
    for s in skills:
        assert s.extends is None
