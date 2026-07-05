"""Builtin filesystem primitives (move/delete/mkdir) for the interactive agent.

`move_file` is additionally covered via the organize re-export in
`test_organize.py`; here we cover the new `delete_file` / `make_dir`, the
writable-zone gating (M189: llm-wiki declares no zones, so it's permissive —
mechanism enforcement for packs that DO declare zones is covered in
`test_layout_writable.py`), and `[run]` membership — the fix for the
interactive surface having no first-class move/rename/delete.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.context import reset_active_project, set_active_project
from veles.core.layout import clear_engine_cache
from veles.core.project import init_project
from veles.core.tools.builtin.file_ops import delete_file, make_dir, move_file
from veles.core.tools.registry import registry
from veles.core.tools.toolsets import TOOLSETS


@pytest.fixture(autouse=True)
def _fresh_engine_cache():
    clear_engine_cache()
    yield
    clear_engine_cache()


@pytest.fixture()
def wiki_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    p = init_project(tmp_path / "proj", name="proj", layout="llm-wiki")
    (p.root / "wiki" / "concepts").mkdir(parents=True, exist_ok=True)
    (p.root / "sources").mkdir(parents=True, exist_ok=True)
    token = set_active_project(p)
    yield p
    reset_active_project(token)


def test_registered_and_in_run_toolset() -> None:
    for name in ("move_file", "delete_file", "make_dir"):
        assert registry.get(name) is not None
        assert name in TOOLSETS["run"]


def test_delete_file_removes_within_writable_zone(wiki_project) -> None:
    f = wiki_project.root / "wiki" / "concepts" / "gone.md"
    f.write_text("bye", encoding="utf-8")
    msg = delete_file(str(f))
    assert "deleted" in msg
    assert not f.exists()


def test_delete_file_in_sources_succeeds_under_llm_wiki(wiki_project) -> None:
    """M189: llm-wiki declares no writable_zones, so `sources/` is no
    longer hard-readonly — deleting there is now permitted."""
    f = wiki_project.root / "sources" / "keep.md"
    f.write_text("original", encoding="utf-8")
    msg = delete_file(str(f))
    assert "deleted" in msg
    assert not f.exists()


def test_delete_file_errors_on_dir_and_missing(wiki_project) -> None:
    d = wiki_project.root / "wiki" / "concepts"
    assert "directory" in delete_file(str(d))  # refuses a directory
    missing = wiki_project.root / "wiki" / "concepts" / "nope.md"
    assert "does not exist" in delete_file(str(missing))


def test_make_dir_creates_nested_in_writable_zone(wiki_project) -> None:
    target = wiki_project.root / "wiki" / "projects" / "work"
    msg = make_dir(str(target))
    assert "created directory" in msg
    assert target.is_dir()
    # Idempotent — a second call still succeeds.
    assert "created directory" in make_dir(str(target))


def test_make_dir_in_sources_succeeds_under_llm_wiki(wiki_project) -> None:
    """M189: llm-wiki declares no writable_zones — `sources/` is writable
    now, so creating a directory there is permitted too."""
    target = wiki_project.root / "sources" / "newdir"
    msg = make_dir(str(target))
    assert "created directory" in msg
    assert target.is_dir()


def test_move_file_creates_nested_parents(wiki_project) -> None:
    src = wiki_project.root / "wiki" / "concepts" / "n.md"
    src.write_text("# N\n", encoding="utf-8")
    dst = wiki_project.root / "wiki" / "projects" / "work" / "n.md"  # nested, parents missing
    msg = move_file(str(src), str(dst))
    assert "moved" in msg
    assert dst.is_file() and not src.exists()
