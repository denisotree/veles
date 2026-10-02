"""M175 — `veles organize`: layout-driven reorg as a built-in module.

Covers: operation resolution per layout, the path-guarded `move_file`
primitive, and the no-op exit on a layout without an organize operation.
(The llm-wiki/notes recipes and `wiki_rename_page` are tested in the registry.)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from veles.core.context import reset_active_project, set_active_project
from veles.core.layout import clear_engine_cache
from veles.core.project import init_project
from veles.modules.organize.dispatcher import resolve_operation
from veles.modules.organize.tools import move_file


@pytest.fixture(autouse=True)
def _fresh_engine_cache():
    clear_engine_cache()
    yield
    clear_engine_cache()


@pytest.fixture()
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


# ---- operation resolution (layout-driven dispatch) ----


def test_pack_operation_resolves_to_its_skill(isolated_home: Path, tmp_path: Path) -> None:
    pack = isolated_home / ".veles" / "layouts" / "tidy"
    (pack / "skills" / "tidy-up").mkdir(parents=True)
    (pack / "layout.toml").write_text(
        '[layout]\nname = "tidy"\n[[layout.operations]]\nname = "organize"\nskill = "tidy-up"\n',
        encoding="utf-8",
    )
    (pack / "skills" / "tidy-up" / "SKILL.md").write_text(
        "---\nname: tidy-up\ndescription: Sort notes/ by topic.\n---\n\nMove files under notes/.\n",
        encoding="utf-8",
    )
    p = init_project(tmp_path / "t", name="t", layout="tidy")
    resolved = resolve_operation(p, "organize")
    assert resolved is not None
    assert resolved.skill == "tidy-up"
    assert "notes/" in resolved.body


def test_bare_has_no_organize_operation(isolated_home: Path, tmp_path: Path) -> None:
    p = init_project(tmp_path / "b", name="b", layout="bare")
    assert resolve_operation(p, "organize") is None


def test_organize_on_bare_exits_two(isolated_home: Path, tmp_path: Path, capsys) -> None:
    from veles.cli.commands.organize import cmd_organize

    p = init_project(tmp_path / "b2", name="b2", layout="bare")
    args = argparse.Namespace(provider="openrouter", model=None, apply=False, scope=None)
    rc = cmd_organize(args, p)
    assert rc == 2
    assert "no" in capsys.readouterr().err.lower()


# ---- move_file primitive (path-guarded) ----


@pytest.fixture()
def wiki_project(isolated_home: Path, tmp_path: Path):
    p = init_project(tmp_path / "proj", name="proj")
    (p.root / "wiki" / "concepts").mkdir(parents=True, exist_ok=True)
    (p.root / "wiki" / "entities").mkdir(parents=True, exist_ok=True)
    token = set_active_project(p)
    yield p
    reset_active_project(token)


def test_move_file_within_writable_zone(wiki_project) -> None:
    src = wiki_project.root / "wiki" / "concepts" / "a.md"
    src.write_text("# A\n", encoding="utf-8")
    dst = wiki_project.root / "wiki" / "entities" / "a.md"
    msg = move_file(str(src), str(dst))
    assert "moved" in msg
    assert not src.exists()
    assert dst.read_text(encoding="utf-8") == "# A\n"


def test_move_file_to_project_root_succeeds(wiki_project) -> None:
    """M189: a pack that declares no writable_zones is permissive — moving a
    file to a bare project-root path is not refused."""
    src = wiki_project.root / "wiki" / "concepts" / "b.md"
    src.write_text("# B\n", encoding="utf-8")
    dst = wiki_project.root / "escaped.md"
    msg = move_file(str(src), str(dst))
    assert "moved" in msg
    assert not src.exists()
    assert dst.read_text(encoding="utf-8") == "# B\n"


def test_move_file_errors_on_existing_dst(wiki_project) -> None:
    src = wiki_project.root / "wiki" / "concepts" / "c.md"
    src.write_text("c", encoding="utf-8")
    dst = wiki_project.root / "wiki" / "entities" / "c.md"
    dst.write_text("existing", encoding="utf-8")
    msg = move_file(str(src), str(dst))
    assert "error" in msg
    assert src.exists()


# ---- toolset wiring ----


def test_toolset_membership() -> None:
    from veles.core.tools.toolsets import TOOLSETS

    assert "move_file" in TOOLSETS["organize"]
    # propose mode uses the read-only builtin set — no mutation tools.
    assert "move_file" not in TOOLSETS["builtin"]
