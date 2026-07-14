"""M214 — dream step that materialises definite dated events as reminders."""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

from veles.core.dreaming import DreamResult, _step_proactive_events
from veles.core.project import init_project
from veles.core.provider import ProviderResponse, TokenUsage
from veles.core.tasks_store import TasksStore

_NOW = _dt.datetime(2026, 7, 14, 22, 0, tzinfo=_dt.UTC).timestamp()


class _FakeProvider:
    supports_tools = False

    def __init__(self, reply: str) -> None:
        self._reply = reply

    def create_message(self, messages, tools=None, *, model, max_tokens=4096) -> ProviderResponse:
        return ProviderResponse(text=self._reply, tool_calls=[], usage=TokenUsage())


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
        lambda: "user: enable BC GAME live tonight at midnight",
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
    loader = lambda: "user: BC GAME live at midnight"  # noqa: E731
    for _ in range(3):
        _step_proactive_events(
            project,
            _FakeProvider(_reply_one()),
            "m",
            loader,
            DreamResult(),
            now=_NOW,
            dry_run=False,
        )
    assert len(_dream_tasks(project)) == 1  # no duplicates across repeated dreams


def test_step_empty_digest_is_noop(tmp_path: Path):
    project = init_project(tmp_path, name="p")
    result = DreamResult()
    _step_proactive_events(
        project, _FakeProvider(_reply_one()), "m", lambda: "", result, now=_NOW, dry_run=False
    )
    assert result.proactive_events == 0
    assert _dream_tasks(project) == []


def test_step_dry_run_extracts_but_does_not_write(tmp_path: Path):
    project = init_project(tmp_path, name="p")
    result = DreamResult()
    _step_proactive_events(
        project, _FakeProvider(_reply_one()), "m", lambda: "corpus", result, now=_NOW, dry_run=True
    )
    assert result.proactive_events == 1  # discovered
    assert _dream_tasks(project) == []  # but not persisted
