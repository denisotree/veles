"""M214 — dream step that materialises definite dated events as reminders."""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

from veles.core.dreaming import DreamResult, _step_proactive_events
from veles.core.project import init_project
from veles.core.provider import Message, ProviderResponse, TokenUsage
from veles.core.tasks_store import TasksStore

_NOW = _dt.datetime(2026, 7, 14, 22, 0, tzinfo=_dt.UTC).timestamp()


class _FakeProvider:
    supports_tools = False

    def __init__(self, reply: str) -> None:
        self._reply = reply

    def create_message(self, messages, tools=None, *, model, max_tokens=4096) -> ProviderResponse:
        return ProviderResponse(text=self._reply, tool_calls=[], usage=TokenUsage())


def _loader():
    """A history_loader yielding (session_id, messages) — the corpus source."""
    return [("s1", [Message(role="user", content="turn on BC GAME live tonight at midnight")])]


def _reply_one() -> str:
    when = _dt.datetime.fromtimestamp(_NOW + 7200, tz=_dt.UTC).isoformat()
    return f'[{{"title": "BC GAME live", "when": "{when}", "note": "merchant"}}]'


def _dream_tasks(project) -> list:
    store = TasksStore(project.memory_db_path)
    try:
        return store.list_tasks(state=None, source="dream")
    finally:
        store.close()


def test_step_materialises_definite_event(tmp_path: Path):
    project = init_project(tmp_path, name="p")
    result = DreamResult()
    _step_proactive_events(
        project,
        _FakeProvider(_reply_one()),
        "stub-model",
        _loader,
        result,
        now=_NOW,
        dry_run=False,
    )
    assert result.proactive_events == 1
    tasks = _dream_tasks(project)
    assert len(tasks) == 1
    assert tasks[0].title == "BC GAME live"
    assert tasks[0].source == "dream"
    assert tasks[0].deliver_to is None  # target resolved later, at delivery
    assert tasks[0].due_at is not None and tasks[0].due_at > _NOW


def test_step_is_idempotent_across_cycles(tmp_path: Path):
    project = init_project(tmp_path, name="p")
    for _ in range(3):
        _step_proactive_events(
            project,
            _FakeProvider(_reply_one()),
            "m",
            _loader,
            DreamResult(),
            now=_NOW,
            dry_run=False,
        )
    assert len(_dream_tasks(project)) == 1  # no duplicates across repeated dreams


def test_step_empty_corpus_is_noop(tmp_path: Path):
    project = init_project(tmp_path, name="p")
    result = DreamResult()
    _step_proactive_events(
        project, _FakeProvider(_reply_one()), "m", lambda: [], result, now=_NOW, dry_run=False
    )
    assert result.proactive_events == 0
    assert _dream_tasks(project) == []


def test_corpus_is_independent_of_curation_cursor(tmp_path: Path):
    """Regression: the proactive corpus must NOT come from the curation-cursor
    loader (`list_sessions_since(last_curated_at)`) — once a session is curated
    the cursor advances past it and that loader goes empty, silently killing
    extraction on an active daemon. The proactive loader uses `list_sessions`
    (recent-activity window), which stays populated regardless of the cursor."""
    from veles.core.dreaming import _proactive_corpus
    from veles.core.memory import SessionStore
    from veles.core.provider import Message as _Msg

    project = init_project(tmp_path, name="p")
    store = SessionStore(project.memory_db_path)
    try:
        sid = store.create_session()
        store.append_turn(sid, _Msg(role="user", content="enable BC GAME live at 20:00"))
        sess = store.get_session(sid)
        assert sess is not None

        # The curation-cursor loader, AFTER curation advanced the cursor past
        # this session, returns nothing:
        curated_cursor_loader = lambda: [  # noqa: E731
            (s.id, store.load_messages(s.id))
            for s in store.list_sessions_since(sess.last_activity_at)
        ]
        assert _proactive_corpus(curated_cursor_loader) == ""  # would kill extraction

        # The proactive (recent-activity) loader still sees it:
        proactive_loader = lambda: [  # noqa: E731
            (s.id, store.load_messages(s.id)) for s in reversed(store.list_sessions(limit=20))
        ]
        assert "BC GAME live at 20:00" in _proactive_corpus(proactive_loader)
    finally:
        store.close()


def test_step_dry_run_extracts_but_does_not_write(tmp_path: Path):
    project = init_project(tmp_path, name="p")
    result = DreamResult()
    _step_proactive_events(
        project, _FakeProvider(_reply_one()), "m", _loader, result, now=_NOW, dry_run=True
    )
    assert result.proactive_events == 1  # discovered
    assert _dream_tasks(project) == []  # but not persisted
