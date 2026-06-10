"""M74 — mirror_to_session appends a synthetic system turn."""

from __future__ import annotations

from veles.channels.mirror import mirror_to_session
from veles.core.memory import SessionStore


def test_mirror_appends_system_turn():
    store = SessionStore(":memory:")
    sid = store.create_session()
    seq = mirror_to_session(
        store,
        session_id=sid,
        text="job daily-summary finished",
        source="job:daily-summary",
        kind="job",
    )
    assert seq >= 0
    msgs = store.load_messages(sid)
    assert len(msgs) == 1
    assert msgs[0].role == "system"
    content = msgs[0].content or ""
    assert "[mirror:job from job:daily-summary]" in content
    assert "job daily-summary finished" in content


def test_mirror_default_kind_is_delivery():
    store = SessionStore(":memory:")
    sid = store.create_session()
    mirror_to_session(store, session_id=sid, text="hi", source="telegram:42")
    msgs = store.load_messages(sid)
    content = msgs[0].content or ""
    assert "[mirror:delivery from telegram:42]" in content


def test_empty_text_no_op():
    store = SessionStore(":memory:")
    sid = store.create_session()
    seq = mirror_to_session(store, session_id=sid, text="   ", source="x")
    assert seq == -1
    assert store.load_messages(sid) == []
