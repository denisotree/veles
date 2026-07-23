"""M58 — MemoryRouter merge of wiki + turn hits."""

from __future__ import annotations

import time
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


def test_recall_returns_empty_when_query_blank(project: Project) -> None:
    store = SessionStore(project.memory_db_path)
    try:
        out = MemoryRouter(project, store=store).recall("   ", limit=5)
    finally:
        store.close()
    assert out == []


def test_recall_returns_wiki_only_without_store(project: Project) -> None:
    """No store passed = the M22 behaviour (wiki only)."""
    wiki = Wiki(project.wiki_root)
    wiki.write_page(category="concepts", slug="alpha", title="Alpha", content="alpha topic body")
    out = MemoryRouter(project).recall("alpha", limit=5)
    assert any(h.rel_path == "wiki/concepts/alpha.md" for h in out)
    assert not any(h.rel_path.startswith("turn:") for h in out)


def test_recall_pulls_turn_hits_when_store_provided(project: Project) -> None:
    store = SessionStore(project.memory_db_path)
    try:
        sid = store.create_session()
        store.append_turn(sid, Message(role="user", content="recall me uniquephrase42"))
        out = MemoryRouter(project, store=store).recall("uniquephrase42", limit=5)
    finally:
        store.close()
    assert any(h.rel_path.startswith(f"turn:{sid}:") for h in out)


def test_recall_skips_old_turns(project: Project) -> None:
    """Default 30-day cutoff should bury ancient turn hits — once curation has
    run. (M193: the window only applies after the first curator/dream pass; an
    un-curated project keeps all turns since they're the only memory.)"""
    from veles.core.curator_state import CuratorState, save_atomic

    save_atomic(
        project.state_dir / "curator.state.json",
        CuratorState(last_curated_at=time.time(), sessions_curated_total=1),
    )
    store = SessionStore(project.memory_db_path)
    try:
        sid = store.create_session()
        store.append_turn(sid, Message(role="user", content="ancient timestamptest token"))
        old_ts = time.time() - 90 * 86400
        store._conn.execute("UPDATE turns SET created_at = ? WHERE session_id = ?", (old_ts, sid))
        out = MemoryRouter(project, store=store).recall("timestamptest", limit=5)
    finally:
        store.close()
    assert not any(h.rel_path.startswith("turn:") for h in out)


def test_recall_turn_summary_truncates_long_content(project: Project) -> None:
    store = SessionStore(project.memory_db_path)
    try:
        sid = store.create_session()
        huge = "wordwordword " * 100 + "needle"
        store.append_turn(sid, Message(role="user", content=huge))
        out = MemoryRouter(project, store=store).recall("needle", limit=5)
    finally:
        store.close()
    assert out, "expected at least one match"
    turn_hits = [h for h in out if h.rel_path.startswith("turn:")]
    assert turn_hits
    assert len(turn_hits[0].summary) <= 200


def test_recall_caps_at_limit(project: Project) -> None:
    wiki = Wiki(project.wiki_root)
    for i in range(10):
        wiki.write_page(
            category="concepts", slug=f"w{i}", title=f"W{i}", content="overflowtoken body"
        )
    store = SessionStore(project.memory_db_path)
    try:
        sid = store.create_session()
        for i in range(10):
            store.append_turn(sid, Message(role="user", content=f"overflowtoken turn {i}"))
        out = MemoryRouter(project, store=store).recall("overflowtoken", limit=3)
    finally:
        store.close()
    assert len(out) == 3
