"""M117.2: layout-pack discovery across project/user/builtin roots."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.layout.discovery import (
    LAYOUT_DEFAULT,
    builtin_layouts_root,
    discover_layouts,
    find_layout,
)
from veles.core.project import init_project


@pytest.fixture()
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


def _write_pack(root: Path, name: str, *, description: str = "") -> Path:
    pack_dir = root / name
    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / "layout.toml").write_text(
        f"""\
[layout]
name = "{name}"
description = "{description}"
""",
        encoding="utf-8",
    )
    return pack_dir


# ---- builtin pack ----


def test_builtin_llm_wiki_pack_discovered(isolated_home: Path) -> None:
    """The repo ships an llm-wiki pack under `src/veles/layouts/llm-wiki/`.
    With no project/user packs, builtin still appears."""
    packs = discover_layouts(project=None)
    names = [p.manifest.name for p in packs]
    assert LAYOUT_DEFAULT in names
    entry = next(p for p in packs if p.manifest.name == LAYOUT_DEFAULT)
    assert entry.scope == "builtin"


def test_builtin_layouts_root_exists() -> None:
    """Sanity: the resolved root points at the shipped layouts directory."""
    root = builtin_layouts_root()
    assert root.is_dir(), root
    assert (root / LAYOUT_DEFAULT / "layout.toml").is_file()


def test_find_layout_returns_default(isolated_home: Path) -> None:
    entry = find_layout(LAYOUT_DEFAULT, project=None)
    assert entry is not None
    assert entry.manifest.name == LAYOUT_DEFAULT
    assert entry.scope == "builtin"
    # The pack root contains the `skills/` directory (sanity, not strict spec).
    assert (entry.root / "skills").is_dir()


def test_find_layout_unknown_returns_none(isolated_home: Path) -> None:
    assert find_layout("does-not-exist", project=None) is None


# ---- override priority ----


def test_user_pack_overrides_builtin(isolated_home: Path) -> None:
    """A user-level pack with the same name as a builtin shadows it."""
    user_layouts = isolated_home / ".veles" / "layouts"  # mirrors user_home() path
    _write_pack(user_layouts, LAYOUT_DEFAULT, description="user override")

    entry = find_layout(LAYOUT_DEFAULT, project=None)
    assert entry is not None
    assert entry.scope == "user"
    assert entry.manifest.description == "user override"


def test_project_pack_overrides_user_and_builtin(isolated_home: Path, tmp_path: Path) -> None:
    project = init_project(tmp_path / "proj", name="proj")
    # User-level pack
    user_layouts = isolated_home / ".veles" / "layouts"  # mirrors user_home() path
    _write_pack(user_layouts, LAYOUT_DEFAULT, description="user")
    # Project-level pack (highest priority)
    project_layouts = project.root / ".veles" / "layouts"
    _write_pack(project_layouts, LAYOUT_DEFAULT, description="project")

    entry = find_layout(LAYOUT_DEFAULT, project=project)
    assert entry is not None
    assert entry.scope == "project"
    assert entry.manifest.description == "project"


# ---- discovery composition ----


def test_discover_returns_one_entry_per_name(isolated_home: Path, tmp_path: Path) -> None:
    """If both user and builtin have `llm-wiki`, discovery yields the
    user-level one once — not twice."""
    user_layouts = isolated_home / ".veles" / "layouts"  # mirrors user_home() path
    _write_pack(user_layouts, LAYOUT_DEFAULT, description="user")

    packs = discover_layouts(project=None)
    matching = [p for p in packs if p.manifest.name == LAYOUT_DEFAULT]
    assert len(matching) == 1
    assert matching[0].scope == "user"


def test_discover_includes_custom_user_packs(isolated_home: Path) -> None:
    user_layouts = isolated_home / ".veles" / "layouts"  # mirrors user_home() path
    _write_pack(user_layouts, "obsidian-import", description="My Obsidian pack")

    packs = discover_layouts(project=None)
    names = [p.manifest.name for p in packs]
    assert "obsidian-import" in names
    assert LAYOUT_DEFAULT in names  # builtin still present


def test_malformed_pack_silently_skipped(isolated_home: Path, tmp_path: Path) -> None:
    """A directory with a broken layout.toml shouldn't poison the whole
    discovery — the parser raises, the discovery layer drops the entry."""
    user_layouts = isolated_home / ".veles" / "layouts"  # mirrors user_home() path
    user_layouts.mkdir(parents=True)
    bad_pack = user_layouts / "broken"
    bad_pack.mkdir()
    (bad_pack / "layout.toml").write_text('[layout\nname = "x"\n', encoding="utf-8")

    # Discovery still works; LAYOUT_DEFAULT (builtin) is present.
    packs = discover_layouts(project=None)
    names = [p.manifest.name for p in packs]
    assert LAYOUT_DEFAULT in names
    assert "broken" not in names


# ---- builtin pack manifest content ----


def test_llm_wiki_pack_declares_three_operations(isolated_home: Path) -> None:
    """The shipped llm-wiki pack covers ingest/query/lint per VISION §5.2."""
    entry = find_layout(LAYOUT_DEFAULT, project=None)
    assert entry is not None
    op_names = {op.name for op in entry.manifest.operations}
    assert {"ingest", "query", "lint"} <= op_names


def test_llm_wiki_pack_declares_writable_wiki_dir(isolated_home: Path) -> None:
    """wiki/ is writable, sources/ is read-only — the VISION §4 contract
    'sources read-only for the agent' is encoded in the manifest."""
    entry = find_layout(LAYOUT_DEFAULT, project=None)
    assert entry is not None
    writable = entry.manifest.writable_path_strings()
    assert "wiki/" in writable
    # sources/ exists as a readonly zone — not in writable_path_strings.
    sources_zones = [z for z in entry.manifest.writable_zones if z.path == "sources/"]
    assert sources_zones and sources_zones[0].readonly is True


def test_llm_wiki_pack_skill_md_files_exist(isolated_home: Path) -> None:
    """Each declared operation has a matching SKILL.md in the pack root."""
    entry = find_layout(LAYOUT_DEFAULT, project=None)
    assert entry is not None
    for op in entry.manifest.operations:
        skill_md = entry.root / "skills" / op.skill / "SKILL.md"
        assert skill_md.is_file(), (op.skill, skill_md)
