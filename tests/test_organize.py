"""M175 — `veles organize`: layout-driven reorg as a built-in module.

Covers: operation resolution per layout, the path-guarded `move_file`
primitive, `wiki_rename_page` (move + back-reference repair), the no-op
exit on a layout without an organize operation, and the batch-add file
collector.
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


def test_llm_wiki_resolves_organize(isolated_home: Path, tmp_path: Path) -> None:
    p = init_project(tmp_path / "w", name="w", layout="llm-wiki")
    resolved = resolve_operation(p, "organize")
    assert resolved is not None
    assert resolved.skill == "organize"
    assert "wiki" in resolved.body.lower()


def test_notes_resolves_organize(isolated_home: Path, tmp_path: Path) -> None:
    p = init_project(tmp_path / "n", name="n", layout="notes")
    resolved = resolve_operation(p, "organize")
    assert resolved is not None
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
    p = init_project(tmp_path / "proj", name="proj", layout="llm-wiki")
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
    """M189: llm-wiki declares no writable_zones, so it is permissive —
    moving a file to a bare project-root path is no longer refused."""
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


# ---- wiki_rename_page (move + back-reference repair) ----


def test_wiki_rename_page_moves_and_repairs_links(wiki_project) -> None:
    import veles.modules.wiki.tools as wt
    from veles.modules.wiki.wiki import Wiki

    wiki = Wiki(wiki_project.wiki_root)
    wiki.ensure_layout()
    wiki.write_page(category="queries", slug="old-note", title="Old Note", content="raw")
    wiki.write_page(
        category="concepts",
        slug="topic",
        title="Topic",
        content="See [[old-note]] for context.",
    )

    msg = wt.wiki_rename_page("wiki/queries/old-note.md", "concepts", "new-note")
    assert "renamed" in msg
    assert (wiki_project.wiki_root / "wiki" / "concepts" / "new-note.md").is_file()
    assert not (wiki_project.wiki_root / "wiki" / "queries" / "old-note.md").exists()
    topic = (wiki_project.wiki_root / "wiki" / "concepts" / "topic.md").read_text(encoding="utf-8")
    assert "[[new-note]]" in topic
    assert "[[old-note]]" not in topic


# ---- toolset wiring ----


def test_toolset_membership() -> None:
    from veles.core.tools.toolsets import TOOLSETS

    assert "move_file" in TOOLSETS["organize"]
    assert "wiki_rename_page" in TOOLSETS["engine-wiki"]
    # propose mode uses the read-only builtin set — no mutation tools.
    assert "move_file" not in TOOLSETS["builtin"]


# ---- batch add file collection ----


def test_batch_ingest_skips_dot_dirs(tmp_path: Path) -> None:
    # M204: the collector moved to the module kernel (shared by CLI + wiki_add).
    from veles.modules.wiki.ingest import batch_ingest_files as _batch_ingest_files

    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("a", encoding="utf-8")
    (tmp_path / "docs" / "b.md").write_text("b", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config.md").write_text("x", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("t", encoding="utf-8")

    md = _batch_ingest_files(tmp_path, "*.md")
    names = {p.name for p in md}
    assert names == {"a.md", "b.md"}  # .git/config.md and notes.txt excluded
