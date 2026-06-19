"""Unit tests for the SQLite FTS5 layer in veles.modules.wiki.wiki."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from veles.modules.wiki.wiki import Wiki, _fts_escape


def _make_wiki(tmp_path: Path) -> Wiki:
    return Wiki(tmp_path)


def test_fts_db_created_lazily_on_first_write(tmp_path: Path) -> None:
    w = _make_wiki(tmp_path)
    assert not (tmp_path / "wiki_index.db").exists()
    w.write_page(
        category="concepts",
        slug="alpha",
        title="Alpha",
        content="The first concept page.",
    )
    assert (tmp_path / "wiki_index.db").is_file()


def test_write_page_upserts_fts(tmp_path: Path) -> None:
    w = _make_wiki(tmp_path)
    w.write_page(category="concepts", slug="a", title="Alpha", content="Foo content.")
    w.write_page(category="concepts", slug="a", title="Alpha v2", content="Bar content.")
    conn = sqlite3.connect(str(tmp_path / "wiki_index.db"))
    rows = conn.execute(
        "SELECT title FROM wiki_fts WHERE rel_path = 'wiki/concepts/a.md'"
    ).fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0][0] == "Alpha v2"


def test_search_uses_fts(tmp_path: Path) -> None:
    w = _make_wiki(tmp_path)
    w.write_page(
        category="concepts",
        slug="zaslon",
        title="Zaslon Concept",
        content="The zaslon term has nothing to do with anything else.",
    )
    w.write_page(
        category="concepts",
        slug="other",
        title="Other Concept",
        content="Completely unrelated material here.",
    )
    hits = w.search("zaslon")
    assert len(hits) == 1
    assert hits[0].slug == "zaslon"


def test_search_falls_back_to_substring_on_empty_index(tmp_path: Path) -> None:
    w = _make_wiki(tmp_path)
    w.write_page(category="concepts", slug="x", title="X", content="Mentions cookies.")
    # Manually drop the FTS db; close connection first
    w.close()
    (tmp_path / "wiki_index.db").unlink()
    w2 = _make_wiki(tmp_path)
    hits = w2.search("cookies")
    assert len(hits) == 1
    # Index should be re-populated after the search
    assert (tmp_path / "wiki_index.db").is_file()
    w2.close()


def test_search_handles_special_chars(tmp_path: Path) -> None:
    w = _make_wiki(tmp_path)
    w.write_page(
        category="concepts",
        slug="x",
        title="Special",
        content="Mentions foo-bar baz.",
    )
    hits = w.search("foo-bar OR baz")
    # Doesn't crash; either hits or empty list is fine.
    assert isinstance(hits, list)


def test_search_unicode(tmp_path: Path) -> None:
    w = _make_wiki(tmp_path)
    w.write_page(
        category="concepts",
        slug="veles",
        title="Velles concept",
        content="Velles is the Slavic mythology god of earth and water.",
    )
    hits = w.search("Velles")
    assert any(h.slug == "veles" for h in hits)


def test_reindex_rebuilds_from_disk(tmp_path: Path) -> None:
    w = _make_wiki(tmp_path)
    # Write via Veles to bootstrap layout.
    w.write_page(category="concepts", slug="a", title="A", content="x")
    # Add a file directly on disk (bypassing FTS upsert).
    direct_page = tmp_path / "wiki" / "entities" / "direct.md"
    direct_page.write_text("# Direct entity\n\nManually added.\n", encoding="utf-8")
    count = w.reindex()
    assert count == 2
    hits = w.search("Manually")
    assert any(h.slug == "direct" for h in hits)


def test_reindex_clears_orphan_rows(tmp_path: Path) -> None:
    w = _make_wiki(tmp_path)
    w.write_page(category="concepts", slug="ghost", title="Ghost", content="haunting")
    # Remove the file directly.
    (tmp_path / "wiki" / "concepts" / "ghost.md").unlink()
    # Before reindex, orphan row still in FTS:
    conn = sqlite3.connect(str(tmp_path / "wiki_index.db"))
    pre = conn.execute("SELECT COUNT(*) FROM wiki_fts").fetchone()[0]
    conn.close()
    assert pre == 1
    w.reindex()
    conn = sqlite3.connect(str(tmp_path / "wiki_index.db"))
    post = conn.execute("SELECT COUNT(*) FROM wiki_fts").fetchone()[0]
    conn.close()
    assert post == 0


def test_search_returns_empty_for_no_match(tmp_path: Path) -> None:
    w = _make_wiki(tmp_path)
    w.write_page(category="concepts", slug="a", title="Alpha", content="x")
    assert w.search("totally-different-token") == []


def test_close_releases_fts_connection(tmp_path: Path) -> None:
    w = _make_wiki(tmp_path)
    w.write_page(category="concepts", slug="a", title="A", content="x")
    w.close()
    # After close, calling search reopens lazily.
    hits = w.search("A")
    assert isinstance(hits, list)


def test_fts_escape_quotes_each_token() -> None:
    assert _fts_escape("foo bar") == '"foo" "bar"'
    assert _fts_escape("") == ""
    assert _fts_escape('foo "bar baz"') == '"foo" """bar" "baz"""'
