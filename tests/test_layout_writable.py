"""M117c-final: layout-pack writable_zones runtime checker."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.layout.writable import is_writable, writable_zones
from veles.core.project import init_project, load_project


@pytest.fixture()
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


# ---- llm-wiki defaults ----


def test_wiki_path_writable_under_llm_wiki(isolated_home: Path, tmp_path: Path) -> None:
    """The default llm-wiki pack declares `wiki/` as writable."""
    project = init_project(tmp_path / "proj", name="proj")
    assert is_writable(project, "wiki/concepts/foo.md")
    assert is_writable(project, "wiki/queries/bar.md")


def test_sources_readonly_under_llm_wiki(isolated_home: Path, tmp_path: Path) -> None:
    """The default llm-wiki pack declares `sources/` as readonly."""
    project = init_project(tmp_path / "proj", name="proj")
    assert not is_writable(project, "sources/raw_dump.txt")
    assert not is_writable(project, "sources/subdir/file.md")


def test_veles_state_always_writable(isolated_home: Path, tmp_path: Path) -> None:
    """`.veles/` is always writable, even if the pack doesn't list it."""
    project = init_project(tmp_path / "proj", name="proj")
    assert is_writable(project, ".veles/memory.db")
    assert is_writable(project, ".veles/tmp/clipboard.txt")
    assert is_writable(project, ".veles/skills/my_skill/SKILL.md")


def test_arbitrary_root_file_not_writable(isolated_home: Path, tmp_path: Path) -> None:
    """Files in the project root but outside declared zones aren't
    writable under llm-wiki."""
    project = init_project(tmp_path / "proj", name="proj")
    assert not is_writable(project, "README.md")
    assert not is_writable(project, "src/main.py")


# ---- permissive fallback ----


def test_unknown_layout_permissive(isolated_home: Path, tmp_path: Path) -> None:
    """When the layout-pack doesn't resolve, fall back to permissive
    (anything inside the project root is writable). Preserves the
    pre-M117 contract."""
    project = init_project(tmp_path / "proj", name="proj")
    toml_path = project.project_toml_path
    text = toml_path.read_text(encoding="utf-8")
    toml_path.write_text(
        text.replace('layout = "llm-wiki"', 'layout = "ghost-pack"'),
        encoding="utf-8",
    )
    reloaded = load_project(project.root)
    assert is_writable(reloaded, "README.md")
    assert is_writable(reloaded, "src/main.py")
    # .veles/ still writable in permissive mode
    assert is_writable(reloaded, ".veles/memory.db")


# ---- outside the project tree ----


def test_outside_project_root_not_writable(isolated_home: Path, tmp_path: Path) -> None:
    """Defence in depth — path_guard catches it earlier, but is_writable
    also says no when the path resolves outside the project root."""
    project = init_project(tmp_path / "proj", name="proj")
    outside = (tmp_path / "elsewhere" / "file.txt").resolve()
    outside.parent.mkdir(parents=True, exist_ok=True)
    assert not is_writable(project, str(outside))


# ---- writable_zones diagnostic ----


def test_writable_zones_includes_pack_and_defaults(isolated_home: Path, tmp_path: Path) -> None:
    project = init_project(tmp_path / "proj", name="proj")
    zones = writable_zones(project)
    # Always-writable defaults first
    assert any(".veles" in z for z in zones)
    # Pack-declared wiki/ also there
    assert any("wiki" in z for z in zones)
    # sources/ (readonly) is NOT in writable list
    assert not any(z.rstrip("/") == "sources" for z in zones)


def test_writable_zones_permissive_when_no_pack(isolated_home: Path, tmp_path: Path) -> None:
    """No pack resolves → writable_zones returns just the always-on
    defaults (callers know to treat empty pack list as permissive)."""
    project = init_project(tmp_path / "proj", name="proj")
    toml_path = project.project_toml_path
    toml_path.write_text(
        toml_path.read_text(encoding="utf-8").replace(
            'layout = "llm-wiki"', 'layout = "ghost-pack"'
        ),
        encoding="utf-8",
    )
    reloaded = load_project(project.root)
    zones = writable_zones(reloaded)
    # Just the always-writable defaults
    assert any(".veles" in z for z in zones)
    assert not any("wiki" in z for z in zones)


# ---- path normalisation ----


def test_absolute_path_inside_project_writable(isolated_home: Path, tmp_path: Path) -> None:
    project = init_project(tmp_path / "proj", name="proj")
    abs_wiki = project.root / "wiki" / "x.md"
    assert is_writable(project, str(abs_wiki))


def test_dotdot_resolved_against_project_root(isolated_home: Path, tmp_path: Path) -> None:
    """`wiki/../sources/foo` resolves to `sources/foo` — readonly."""
    project = init_project(tmp_path / "proj", name="proj")
    assert not is_writable(project, "wiki/../sources/foo.txt")
