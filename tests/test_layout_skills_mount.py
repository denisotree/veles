"""M117b: layout-pack skills mount into discover_skills.

A project's active layout-pack contributes its `skills/<name>/SKILL.md`
files to the discover list, at builtin priority (overridden by project
and user level) — agent-callable without any wiring.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.project import init_project, load_project
from veles.core.skills import discover_skills, mount_layout_skills


def _write_skill(
    skills_dir: Path, name: str, body: str, *, description: str = "", tools: str = ""
) -> None:
    sd = skills_dir / name
    sd.mkdir(parents=True, exist_ok=True)
    extra = f"tools: [{tools}]\n" if tools else ""
    fm = f"---\nname: {name}\ndescription: {description or f'skill {name}'}\n{extra}---\n{body}\n"
    (sd / "SKILL.md").write_text(fm, encoding="utf-8")


@pytest.fixture()
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A user home with a `skilled` layout pack shipping ingest / query / lint."""
    home = tmp_path / "home"
    monkeypatch.setenv("VELES_USER_HOME", str(home))
    pack = home / ".veles" / "layouts" / "skilled"
    pack.mkdir(parents=True)
    (pack / "layout.toml").write_text('[layout]\nname = "skilled"\n', encoding="utf-8")
    _write_skill(pack / "skills", "ingest", "pack ingest", tools="read_file, write_file")
    _write_skill(pack / "skills", "query", "pack query")
    _write_skill(pack / "skills", "lint", "pack lint")
    return home


def _project(tmp_path: Path):
    return init_project(tmp_path / "proj", name="proj", layout="skilled")


# ---- mount_layout_skills directly ----


def test_pack_skills_discovered(isolated_home: Path, tmp_path: Path) -> None:
    names = {s.name for s in mount_layout_skills(_project(tmp_path))}
    assert {"ingest", "query", "lint"} <= names


def test_pack_skills_have_builtin_scope(isolated_home: Path, tmp_path: Path) -> None:
    for s in mount_layout_skills(_project(tmp_path)):
        assert s.scope == "builtin"


def test_pack_skill_has_expected_tools(isolated_home: Path, tmp_path: Path) -> None:
    by_name = {s.name: s for s in mount_layout_skills(_project(tmp_path))}
    assert "read_file" in by_name["ingest"].tools


def test_unknown_layout_returns_empty(isolated_home: Path, tmp_path: Path) -> None:
    """If the project points at a layout that doesn't exist, we don't
    crash — we return an empty list and let the agent run with just
    project + user skills."""
    project = _project(tmp_path)
    toml_path = project.project_toml_path
    text = toml_path.read_text(encoding="utf-8")
    toml_path.write_text(
        text.replace('layout = "skilled"', 'layout = "ghost-pack"'), encoding="utf-8"
    )
    reloaded = load_project(project.root)
    assert reloaded.layout_name == "ghost-pack"
    assert mount_layout_skills(reloaded) == []


# ---- discover_skills integration ----


def test_discover_skills_includes_layout_pack(isolated_home: Path, tmp_path: Path) -> None:
    names = {s.name for s in discover_skills(_project(tmp_path), include_layout=True)}
    assert {"ingest", "query", "lint"} <= names


def test_project_skill_shadows_pack_skill(isolated_home: Path, tmp_path: Path) -> None:
    """The override invariant: project > user > pack."""
    project = _project(tmp_path)
    _write_skill(
        project.skills_dir, "ingest", "project-local ingest body", description="project override"
    )
    by_name = {s.name: s for s in discover_skills(project, include_layout=True)}
    assert by_name["ingest"].scope == "project"
    assert "project-local ingest body" in by_name["ingest"].body


def test_user_skill_shadows_pack_skill(isolated_home: Path, tmp_path: Path) -> None:
    project = _project(tmp_path)
    _write_skill(isolated_home / ".veles" / "skills", "query", "user-level query body")
    by_name = {s.name: s for s in discover_skills(project, include_layout=True)}
    assert by_name["query"].scope == "user"
    assert "user-level query body" in by_name["query"].body


def test_project_shadows_user_shadows_pack(isolated_home: Path, tmp_path: Path) -> None:
    project = _project(tmp_path)
    _write_skill(isolated_home / ".veles" / "skills", "lint", "user lint body")
    _write_skill(project.skills_dir, "lint", "project lint body")
    by_name = {s.name: s for s in discover_skills(project, include_layout=True)}
    assert by_name["lint"].scope == "project"


def test_pack_skill_with_extends_field_loaded(isolated_home: Path, tmp_path: Path) -> None:
    """Pack SKILL.md goes through the same parser as every other scope, so a
    pack skill without `extends:` loads standalone."""
    for s in mount_layout_skills(_project(tmp_path)):
        assert s.extends is None
