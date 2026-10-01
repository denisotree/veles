"""M84: `Wiki.is_index_stale` + `reindex_if_stale` + dream's reindex step."""

from __future__ import annotations

import os
import time
from pathlib import Path

from veles.core.dreaming import DreamResult
from veles.modules.wiki.wiki import Wiki


def _make_wiki(tmp_path: Path) -> Wiki:
    wiki = Wiki(tmp_path)
    wiki.ensure_layout()
    return wiki


def test_is_stale_when_no_db(tmp_path: Path) -> None:
    wiki = _make_wiki(tmp_path)
    wiki.write_page(category="concepts", slug="a", title="A", content="body")
    # Drop the FTS db so the next stale check triggers a rebuild.
    db = tmp_path / "wiki_index.db"
    if db.exists():
        db.unlink()
    assert wiki.is_index_stale() is True


def test_reindex_if_stale_returns_zero_when_fresh(tmp_path: Path) -> None:
    wiki = _make_wiki(tmp_path)
    wiki.write_page(category="concepts", slug="alpha", title="Alpha", content="body")
    # First call rebuilds; second should see a fresh db and return 0.
    wiki.reindex()
    assert wiki.reindex_if_stale(max_age_sec=3600) == 0


def test_reindex_if_stale_rebuilds_on_newer_file(tmp_path: Path) -> None:
    wiki = _make_wiki(tmp_path)
    wiki.write_page(category="concepts", slug="alpha", title="Alpha", content="body")
    wiki.reindex()
    # Touch a wiki file with a future mtime so the db looks stale.
    target = tmp_path / "wiki" / "concepts" / "alpha.md"
    future = time.time() + 60
    os.utime(target, (future, future))
    indexed = wiki.reindex_if_stale(max_age_sec=3600)
    assert indexed >= 1


def test_dream_reindex_step_records_count(tmp_path: Path, monkeypatch) -> None:
    """The wiki engine's `reindex` dream step (a contribution since release A)."""
    from veles.core.project import init_project
    from veles.modules.wiki.dream import reindex_step

    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    project = init_project(tmp_path / "p", name="p", layout="llm-wiki")
    wiki = Wiki(project.wiki_root)
    wiki.write_page(category="concepts", slug="a", title="A", content="body")
    # Drop db to guarantee stale path.
    db = project.wiki_root / "wiki_index.db"
    if db.exists():
        db.unlink()
    result = DreamResult()
    reindex_step(project, result, dry_run=False)
    assert result.reindexed_pages >= 1
