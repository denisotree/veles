"""Tests: wiki.write_page stamps untrusted pages with trust frontmatter (M66)."""

from __future__ import annotations

from pathlib import Path

from veles.modules.wiki.wiki import Wiki


def _make_wiki(tmp_path: Path) -> Wiki:
    w = Wiki(tmp_path)
    w.ensure_layout()
    return w


def test_default_authoritative_page_has_no_frontmatter(tmp_path: Path) -> None:
    """Existing authoritative writes keep the original wire shape — body
    starts with the H1 line, nothing prepended. Backward compat for the
    1100+ tests that depend on the current layout."""
    w = _make_wiki(tmp_path)
    rel = w.write_page(category="concepts", slug="foo", title="Foo", content="text")
    body = (tmp_path / rel).read_text()
    assert body.startswith("# Foo")
    assert "trust:" not in body
    assert "source_url:" not in body


def test_external_page_gets_trust_frontmatter(tmp_path: Path) -> None:
    w = _make_wiki(tmp_path)
    rel = w.write_page(
        category="concepts",
        slug="bar",
        title="Bar",
        content="from web",
        trust="external",
        source_url="https://example.com/article",
    )
    body = (tmp_path / rel).read_text()
    assert body.startswith("---\n")
    assert "trust: external" in body
    assert 'source_url: "https://example.com/article"' in body
    # The H1 still lands after the closing `---\n\n`.
    assert "\n\n# Bar" in body


def test_explicit_non_external_trust_writes_minimal_frontmatter(tmp_path: Path) -> None:
    """If the caller wants `trust: cached` or `trust: verified`, that lands
    as-is in a minimal frontmatter block — no source_url machinery."""
    w = _make_wiki(tmp_path)
    rel = w.write_page(
        category="entities",
        slug="x",
        title="X",
        content="text",
        trust="verified",
    )
    body = (tmp_path / rel).read_text()
    assert "trust: verified" in body
    assert "source_url:" not in body
