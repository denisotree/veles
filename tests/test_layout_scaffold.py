"""M162 — pack-driven init scaffold + engine resolution.

`init_project(layout=...)` delegates the user-content skeleton to the
chosen layout pack: scaffold dirs and the AGENTS.md template (engine
trees, e.g. the wiki's, come from the engine module's `scaffold`).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.layout import (
    apply_scaffold,
    clear_engine_cache,
    engine_enabled,
    find_layout,
)
from veles.core.project import init_project


def wiki_enabled(project) -> bool:
    return engine_enabled(project, "wiki")


@pytest.fixture(autouse=True)
def _fresh_engine_cache():
    clear_engine_cache()
    yield
    clear_engine_cache()


def _write_pack(root: Path, name: str, body: str) -> None:
    pack_dir = root / "layouts" / name
    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / "layout.toml").write_text(body, encoding="utf-8")


@pytest.fixture()
def user_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # VELES_USER_HOME replaces `~` (HOME), not `.veles` itself.
    home = tmp_path / "home"
    (home / ".veles").mkdir(parents=True)
    monkeypatch.setenv("VELES_USER_HOME", str(home))
    return home / ".veles"


# ---- custom pack without the wiki engine ----


def test_init_custom_pack_scaffolds_only_declared_dirs(tmp_path: Path, user_home: Path) -> None:
    _write_pack(
        user_home,
        "flat-notes",
        '[layout]\nname = "flat-notes"\n'
        '[layout.scaffold]\ndirs = ["notes/"]\n'
        '[[layout.writable_zones]]\npath = "notes/"\n',
    )
    project = init_project(tmp_path / "p", name="p", layout="flat-notes")
    assert (project.root / "notes").is_dir()
    assert not (project.root / "wiki").exists()
    assert not (project.root / "sources").exists()
    assert not wiki_enabled(project)
    assert project.layout_name == "flat-notes"
    # Layout-agnostic default AGENTS.md (no pack template declared).
    agents = (project.root / "AGENTS.md").read_text(encoding="utf-8")
    assert "## Layout" in agents
    assert "wiki/" not in agents


def test_init_unknown_layout_degrades_to_bare(tmp_path: Path, capsys) -> None:
    project = init_project(tmp_path / "p", name="p", layout="no-such-pack")
    assert not (project.root / "wiki").exists()
    assert (project.root / "AGENTS.md").is_file()
    assert not wiki_enabled(project)
    assert "not found" in capsys.readouterr().err


def test_pack_agents_md_template_substitutes_name(tmp_path: Path, user_home: Path) -> None:
    _write_pack(
        user_home,
        "tpl",
        '[layout]\nname = "tpl"\n[layout.scaffold]\nagents_md_template = "templates/AGENTS.md"\n',
    )
    tpl_dir = user_home / "layouts" / "tpl" / "templates"
    tpl_dir.mkdir(parents=True)
    (tpl_dir / "AGENTS.md").write_text(
        "# {name}\n\n## Layout\n\ncustom\n## Conventions\n\n## Workflows\n",
        encoding="utf-8",
    )
    project = init_project(tmp_path / "p", name="myproj", layout="tpl")
    agents = (project.root / "AGENTS.md").read_text(encoding="utf-8")
    assert agents.startswith("# myproj")
    assert "custom" in agents


def test_apply_scaffold_never_overwrites_agents_md(tmp_path: Path) -> None:
    root = tmp_path / "p"
    root.mkdir()
    (root / "AGENTS.md").write_text("# existing\n", encoding="utf-8")
    pack = find_layout("bare", project=None)
    apply_scaffold(pack, root, "p")
    assert (root / "AGENTS.md").read_text(encoding="utf-8") == "# existing\n"


# ---- engine cache ----


def test_wiki_enabled_tracks_manifest_changes(
    tmp_path: Path, user_home: Path, wiki_engine: str
) -> None:
    import os
    import time

    _write_pack(user_home, "toggle", '[layout]\nname = "toggle"\n')
    project = init_project(tmp_path / "p", name="p", layout="toggle")
    assert not wiki_enabled(project)
    manifest = user_home / "layouts" / "toggle" / "layout.toml"
    manifest.write_text(
        '[layout]\nname = "toggle"\n[layout.engines]\nwiki = true\n',
        encoding="utf-8",
    )
    # Ensure the mtime actually moves on coarse-granularity filesystems.
    future = time.time() + 5
    os.utime(manifest, (future, future))
    assert wiki_enabled(project)


def test_wiki_enabled_false_without_project() -> None:
    assert not wiki_enabled(None)
