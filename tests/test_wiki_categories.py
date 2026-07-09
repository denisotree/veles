"""Manifest-driven, nestable wiki categories.

Categories were a hardcoded tuple (`_ALLOWED_CATEGORIES`) so `wiki/projects/`,
`wiki/diary/`, `wiki/tasks/` and nested paths were rejected by `wiki_write_page`
— the blocker for an extensible wiki layout. Now the allowed roots are the core
defaults plus the active layout pack's `[layout.wiki].categories`, and a category
may be a nested path (`projects/work`).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.layout import clear_engine_cache
from veles.core.layout.manifest import _parse_wiki_categories
from veles.core.project import init_project
from veles.modules.wiki.wiki import _DEFAULT_CATEGORIES, Wiki


@pytest.fixture(autouse=True)
def _fresh_engine_cache():
    clear_engine_cache()
    yield
    clear_engine_cache()


@pytest.fixture()
def wiki_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    return init_project(tmp_path / "proj", name="proj", layout="llm-wiki")


# ---- manifest parsing ----


def test_manifest_parses_wiki_categories(tmp_path: Path) -> None:
    toml = tmp_path / "layout.toml"
    assert _parse_wiki_categories({"categories": ["projects", "projects/work"]}, toml) == (
        "projects",
        "projects/work",
    )
    assert _parse_wiki_categories({}, toml) == ()  # absent → none


def test_manifest_rejects_escaping_category(tmp_path: Path) -> None:
    from veles.core.layout.manifest import LayoutManifestError

    with pytest.raises(LayoutManifestError):
        _parse_wiki_categories({"categories": ["../escape"]}, tmp_path / "layout.toml")


# ---- Wiki resolves categories from the pack ----


def test_builtin_pack_ships_no_project_categories(wiki_project) -> None:
    """The framework hardcodes NO project schema: a fresh llm-wiki project has
    only the generic core categories — diary/tasks/projects are NOT baked in."""
    cats = set(Wiki(wiki_project.wiki_root).categories())
    assert set(_DEFAULT_CATEGORIES) <= cats
    assert not ({"projects", "diary", "tasks"} & cats)  # project-specific, not shipped


def test_sources_is_not_a_wiki_page_category(wiki_project) -> None:
    """M203: `sources/` is the top-level raw-audit tree, NOT a wiki page
    category. It was a weak-model date-dump bucket (`wiki/sources/2025-02-27`)
    that collided with the project-root `sources/` dir, so it's removed from
    the writable wiki roots — ingestion routes to topical categories instead."""
    wiki = Wiki(wiki_project.wiki_root)
    assert "sources" not in wiki.categories()
    with pytest.raises(ValueError, match="category root"):
        wiki.write_page(category="sources", slug="2025-02-27", title="X", content="y")


def test_project_local_categories_are_picked_up(wiki_project) -> None:
    from veles.modules.wiki.wiki import add_project_category

    add_project_category(wiki_project.wiki_root, "diary")
    add_project_category(wiki_project.wiki_root, "projects/work")
    cats = set(Wiki(wiki_project.wiki_root).categories())
    assert {"diary", "projects/work"} <= cats  # declared per-project → available


def test_write_page_to_project_declared_category(wiki_project) -> None:
    from veles.modules.wiki.wiki import add_project_category

    add_project_category(wiki_project.wiki_root, "diary")
    w = Wiki(wiki_project.wiki_root)
    rel = w.write_page(category="diary", slug="2026-07-02", title="Day", content="hi")
    assert rel == "wiki/diary/2026-07-02.md"
    assert (wiki_project.root / rel).is_file()


def test_write_page_nested_category(wiki_project) -> None:
    from veles.modules.wiki.wiki import add_project_category

    add_project_category(wiki_project.wiki_root, "projects")
    w = Wiki(wiki_project.wiki_root)
    rel = w.write_page(category="projects/work", slug="visidata-fork", title="V", content="x")
    assert rel == "wiki/projects/work/visidata-fork.md"
    assert (wiki_project.root / rel).is_file()
    cats = {p.category for p in w.list_pages()}
    assert "projects/work" in cats


def test_write_page_rejects_undeclared_root(wiki_project) -> None:
    w = Wiki(wiki_project.wiki_root)
    with pytest.raises(ValueError, match="category root"):
        w.write_page(category="bogus", slug="x", title="X", content="y")


def test_index_lists_nested_pages(wiki_project) -> None:
    from veles.modules.wiki.wiki import add_project_category

    add_project_category(wiki_project.wiki_root, "projects")
    add_project_category(wiki_project.wiki_root, "diary")
    w = Wiki(wiki_project.wiki_root)
    w.write_page(category="projects/work", slug="a", title="A", content="x")
    w.write_page(category="diary", slug="2026-07-02", title="Day", content="y")
    index = (wiki_project.root / "INDEX.md").read_text(encoding="utf-8")
    assert "## projects/work" in index and "wiki/projects/work/a.md" in index
    assert "## diary" in index


def test_categories_override_for_tests(wiki_project) -> None:
    w = Wiki(wiki_project.wiki_root, categories=("concepts", "custom"))
    assert w.categories() == ("concepts", "custom")
    w.write_page(category="custom", slug="c", title="C", content="z")
    assert (wiki_project.root / "wiki" / "custom" / "c.md").is_file()


# ---- project-local declaration helpers ----


def test_add_project_category_persists_and_dedupes(wiki_project) -> None:
    from veles.modules.wiki.wiki import add_project_category, read_project_categories

    added, cat = add_project_category(wiki_project.wiki_root, "Diary")  # normalizes
    assert added and cat == "diary"
    assert read_project_categories(wiki_project.wiki_root) == ["diary"]
    again, cat2 = add_project_category(wiki_project.wiki_root, "diary")  # idempotent
    assert not again and cat2 == "diary"
    assert read_project_categories(wiki_project.wiki_root) == ["diary"]


def test_add_project_category_refuses_core_default(wiki_project) -> None:
    from veles.modules.wiki.wiki import add_project_category, read_project_categories

    added, cat = add_project_category(wiki_project.wiki_root, "concepts")
    assert not added and cat == "concepts"  # already core — not re-declared
    assert read_project_categories(wiki_project.wiki_root) == []


def test_add_project_category_rejects_unsafe(wiki_project) -> None:
    from veles.modules.wiki.wiki import add_project_category

    added, msg = add_project_category(wiki_project.wiki_root, "../escape")
    assert not added and msg.startswith("<error:")


def test_wiki_add_category_tool_declares_and_creates_dir(wiki_project) -> None:
    from veles.core.context import reset_active_project, set_active_project
    from veles.modules.wiki.tools import wiki_add_category

    token = set_active_project(wiki_project)
    try:
        out = wiki_add_category("meetings")
        assert "meetings" in out
        assert (wiki_project.root / "wiki" / "meetings").is_dir()
        assert "meetings" in Wiki(wiki_project.wiki_root).categories()
    finally:
        reset_active_project(token)
