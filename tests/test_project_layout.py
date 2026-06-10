"""M117.3: Project.layout_name persistence in project.toml."""

from __future__ import annotations

from pathlib import Path

from veles.core.project import init_project, load_project


def test_init_project_sets_default_layout(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    assert project.layout_name == "llm-wiki"
    # project.toml mentions the layout so subsequent loads see it.
    toml = project.project_toml_path.read_text(encoding="utf-8")
    assert 'layout = "llm-wiki"' in toml


def test_load_project_reads_layout_back(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    reloaded = load_project(project.root)
    assert reloaded.layout_name == "llm-wiki"


def test_load_project_handles_missing_layout_field(tmp_path: Path) -> None:
    """Older project.tomls (pre-M117) don't have the `layout` key.
    `load_project` must fall back to the default rather than crash."""
    project = init_project(tmp_path / "p", name="p")
    toml_path = project.project_toml_path
    text = toml_path.read_text(encoding="utf-8")
    # Strip the layout line to mimic a pre-M117 file.
    stripped = "\n".join(
        line for line in text.splitlines() if not line.startswith("layout = ")
    )
    toml_path.write_text(stripped + "\n", encoding="utf-8")
    reloaded = load_project(project.root)
    assert reloaded.layout_name == "llm-wiki"


def test_load_project_custom_layout_value(tmp_path: Path) -> None:
    """When a project.toml is hand-edited to point at another layout
    (e.g. a user-installed `obsidian-import`), `load_project` honours it."""
    project = init_project(tmp_path / "p", name="p")
    toml_path = project.project_toml_path
    text = toml_path.read_text(encoding="utf-8")
    text = text.replace(
        'layout = "llm-wiki"', 'layout = "obsidian-import"'
    )
    toml_path.write_text(text, encoding="utf-8")
    reloaded = load_project(project.root)
    assert reloaded.layout_name == "obsidian-import"
