"""M86: `wiki_ingest` convenience tool — fetch URL / read file + write
wiki page in one call."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from veles.core.context import set_active_project
from veles.core.project import init_project
from veles.core.tools.builtin.wiki_tools import _infer_title_from_text, _kebab


def _project(tmp_path: Path):
    return init_project(tmp_path)


def test_infer_title_picks_first_heading() -> None:
    body = "# Title\n\nbody text"
    assert _infer_title_from_text(body) == "Title"


def test_infer_title_falls_back_to_first_line() -> None:
    body = "Just a plain line\n\nmore"
    assert _infer_title_from_text(body) == "Just a plain line"


def test_kebab_slugifies() -> None:
    assert _kebab("Hello World") == "hello-world"
    assert _kebab("React Hooks 101") == "react-hooks-101"
    assert _kebab("!!Wow!!") == "wow"


def test_wiki_ingest_local_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _project(tmp_path)
    token = set_active_project(project)
    try:
        src = tmp_path / "note.md"
        src.write_text("# My Note\n\nSome content.", encoding="utf-8")
        from veles.core.tools.builtin.wiki_tools import wiki_ingest

        result = wiki_ingest(str(src), slug="my-note", title="My Note")
        assert "wiki/sources/my-note.md" in result
        page = (project.wiki_root / "wiki" / "sources" / "my-note.md").read_text(encoding="utf-8")
        assert "My Note" in page
    finally:
        # set_active_project returns a token but its module's reset signature
        # may differ; instead just rely on test isolation.
        del token


def test_wiki_ingest_url_calls_fetch_and_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _project(tmp_path)
    token = set_active_project(project)
    try:
        # Stub fetch_url so the test stays offline.
        def fake_fetch(url: str, max_bytes: int = 200_000, **kwargs: Any) -> str:
            return f"# Fetched\n\nfrom {url}"

        monkeypatch.setattr("veles.core.tools.builtin.fetch_url.fetch_url", fake_fetch)
        from veles.core.tools.builtin.wiki_tools import wiki_ingest

        result = wiki_ingest("https://example.com/post")
        assert "wiki/sources/fetched.md" in result
        page = (project.wiki_root / "wiki" / "sources" / "fetched.md").read_text(encoding="utf-8")
        assert "from https://example.com/post" in page
        # External source → trust frontmatter present.
        assert "trust" in page
    finally:
        del token


def test_wiki_ingest_respects_explicit_category(tmp_path: Path) -> None:
    project = _project(tmp_path)
    token = set_active_project(project)
    try:
        src = tmp_path / "framework.md"
        src.write_text("# Framework\n\ndetails", encoding="utf-8")
        from veles.core.tools.builtin.wiki_tools import wiki_ingest

        result = wiki_ingest(str(src), category="concepts", slug="framework", title="Framework")
        assert "wiki/concepts/framework.md" in result
    finally:
        del token
