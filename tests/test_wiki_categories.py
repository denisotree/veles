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


def test_llm_wiki_categories_include_pack_extras(wiki_project) -> None:
    cats = Wiki(wiki_project.wiki_root).categories()
    for core in _DEFAULT_CATEGORIES:
        assert core in cats
    assert {"projects", "diary", "tasks"} <= set(cats)  # from [layout.wiki].categories


def test_write_page_to_new_category(wiki_project) -> None:
    w = Wiki(wiki_project.wiki_root)
    rel = w.write_page(category="diary", slug="2026-07-02", title="Day", content="hi")
    assert rel == "wiki/diary/2026-07-02.md"
    assert (wiki_project.root / rel).is_file()


def test_write_page_nested_category(wiki_project) -> None:
    w = Wiki(wiki_project.wiki_root)
    rel = w.write_page(category="projects/work", slug="visidata-fork", title="V", content="x")
    assert rel == "wiki/projects/work/visidata-fork.md"
    assert (wiki_project.root / rel).is_file()
    # The nested page is discovered by list_pages with its nested category.
    cats = {p.category for p in w.list_pages()}
    assert "projects/work" in cats


def test_write_page_rejects_undeclared_root(wiki_project) -> None:
    w = Wiki(wiki_project.wiki_root)
    with pytest.raises(ValueError, match="category root"):
        w.write_page(category="bogus", slug="x", title="X", content="y")


def test_index_lists_nested_pages(wiki_project) -> None:
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
