"""M141: recall reranking reorders by recency (curated wiki still leads).
M223 removed the `VELES_MEMORY_RERANK=0` round-robin fallback — rerank is
unconditional."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.memory import SessionStore
from veles.core.memory.router import MemoryRouter
from veles.core.project import Project, init_project
from veles.core.provider import Message
from veles.modules.wiki.wiki import Wiki


@pytest.fixture()
def project(tmp_path: Path) -> Project:
    return init_project(tmp_path / "demo", name="demo")


def _seed_wiki_and_turn(project: Project, store: SessionStore) -> None:
    wiki = Wiki(project.wiki_root)
    wiki.write_page(category="concepts", slug="theme", title="Theme A", content="commontoken body")
    sid = store.create_session()
    store.append_turn(sid, Message(role="user", content="commontoken happened just now in chat"))


def test_rerank_on_does_not_bury_curated_wiki(project: Project) -> None:
    """M141 (advisor catch): default rerank must not demote the curated wiki
    layer below raw turns. A timeless wiki page ties an equally-fresh turn and
    wins on stream order — curated knowledge still leads."""
    store = SessionStore(project.memory_db_path)
    try:
        _seed_wiki_and_turn(project, store)
        out = MemoryRouter(project, store=store).recall("commontoken", limit=4)
    finally:
        store.close()
    assert out[0].rel_path.startswith("wiki/")


def test_rerank_timeless_wiki_outranks_stale_turn(project: Project) -> None:
    """Cross-source recency: a curated wiki page (timeless) outranks a turn that
    matches but is 20 days old — the stale raw turn sinks below distilled
    knowledge."""
    store = SessionStore(project.memory_db_path)
    try:
        wiki = Wiki(project.wiki_root)
        wiki.write_page(
            category="concepts", slug="t", title="T", content="agedtoken curated knowledge"
        )
        sid = store.create_session()
        store.append_turn(sid, Message(role="user", content="agedtoken mentioned in old chat"))
        store._conn.execute(
            "UPDATE turns SET created_at = ? WHERE session_id=?",
            (__import__("time").time() - 20 * 86400, sid),
        )
        store._conn.commit()
        out = MemoryRouter(project, store=store).recall("agedtoken", limit=5)
    finally:
        store.close()
    assert out[0].rel_path.startswith("wiki/")
