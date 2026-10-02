"""A module ships skills in `skills/<name>/SKILL.md`; they mount for every project
that loads the module, below the project's and the user's own skills."""

from __future__ import annotations

from pathlib import Path

from veles.core.module_loading import load_project_modules
from veles.core.modules import reset_module_registry, set_module_registry
from veles.core.project import Project, init_project
from veles.core.registry.gate import approve_module
from veles.core.skills import discover_skills
from veles.core.user_paths import user_modules_dir, user_skills_dir

_SKILL = "---\nname: {name}\ndescription: {desc}\n---\n\nDo it.\n"


def _module_with_skill(skill: str) -> Path:
    d = user_modules_dir() / "kit"
    (d / "skills" / skill).mkdir(parents=True)
    (d / "module.toml").write_text(
        '[module]\nname = "kit"\ndescription = "d"\nentrypoint = "m.py:register"\n',
        encoding="utf-8",
    )
    (d / "m.py").write_text("def register(api):\n    pass\n", encoding="utf-8")
    (d / "skills" / skill / "SKILL.md").write_text(
        _SKILL.format(name=skill, desc="from the module"), encoding="utf-8"
    )
    approve_module(d, name="kit", project_root=None)
    return d


def _skills(project: Project) -> dict[str, str]:
    token = set_module_registry(load_project_modules(project))
    try:
        return {s.name: s.description for s in discover_skills(project, include_layout=True)}
    finally:
        reset_module_registry(token)


def test_a_loaded_module_mounts_its_skills(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    _module_with_skill("summarise")
    assert _skills(project)["summarise"] == "from the module"


def test_user_skill_wins_over_a_module_skill(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    _module_with_skill("summarise")
    own = user_skills_dir() / "summarise"
    own.mkdir(parents=True)
    (own / "SKILL.md").write_text(_SKILL.format(name="summarise", desc="mine"), encoding="utf-8")
    assert _skills(project)["summarise"] == "mine"


def test_a_skill_edited_after_approval_unloads_the_module(tmp_path: Path) -> None:
    """The approval hash covers the module's skills, not only its code: a changed
    SKILL.md is unreviewed, so the whole module (skills included) stays out."""
    project = init_project(tmp_path / "p", name="p")
    d = _module_with_skill("summarise")
    (d / "skills" / "summarise" / "SKILL.md").write_text(
        _SKILL.format(name="summarise", desc="sneaky"), encoding="utf-8"
    )
    assert "summarise" not in _skills(project)
