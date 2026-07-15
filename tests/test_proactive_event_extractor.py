"""M214 — definite-dated-event extraction from memory (discovery half)."""

from __future__ import annotations

import datetime as _dt

from veles.core.proactive.event_extractor import (
    _dedup_key,
    extract_definite_events,
)
from veles.core.provider import Message, ProviderResponse, TokenUsage


class _FakeProvider:
    """Returns a fixed reply regardless of the prompt; records the messages."""

    supports_tools = False

    def __init__(self, reply: str) -> None:
        self._reply = reply
        self.seen: list[Message] = []

    def create_message(self, messages, tools=None, *, model, max_tokens=4096) -> ProviderResponse:
        self.seen = list(messages)
        return ProviderResponse(text=self._reply, tool_calls=[], usage=TokenUsage())


_NOW = _dt.datetime(2026, 7, 14, 22, 0, tzinfo=_dt.UTC).timestamp()


def _iso(hours_from_now: float) -> str:
    return _dt.datetime.fromtimestamp(_NOW + hours_from_now * 3600, tz=_dt.UTC).isoformat()


def test_extracts_future_dated_event():
    reply = f'[{{"title": "BC GAME live processing", "when": "{_iso(2)}", "note": "merchant"}}]'
    events = extract_definite_events(
        corpus="user: enable BC GAME live at midnight",
        now=_NOW,
        provider=_FakeProvider(reply),
        model="stub",
    )
    assert len(events) == 1
    assert events[0].title == "BC GAME live processing"
    assert events[0].body == "merchant"
    assert events[0].due_at > _NOW


def test_drops_past_events():
    reply = f'[{{"title": "already happened", "when": "{_iso(-5)}"}}]'
    events = extract_definite_events(
        corpus="x", now=_NOW, provider=_FakeProvider(reply), model="stub"
    )
    assert events == []


def test_tolerates_prose_and_code_fences():
    reply = (
        f'Here are the events:\n```json\n[{{"title": "standup", "when": "{_iso(10)}"}}]\n```\nDone.'
    )
    events = extract_definite_events(
        corpus="x", now=_NOW, provider=_FakeProvider(reply), model="stub"
    )
    assert [e.title for e in events] == ["standup"]


def test_empty_reply_and_empty_corpus():
    assert (
        extract_definite_events(corpus="x", now=_NOW, provider=_FakeProvider("[]"), model="s") == []
    )
    # empty corpus short-circuits before any provider call
    p = _FakeProvider("should not be called")
    assert extract_definite_events(corpus="   ", now=_NOW, provider=p, model="s") == []
    assert p.seen == []


def test_malformed_json_yields_nothing():
    events = extract_definite_events(
        corpus="x", now=_NOW, provider=_FakeProvider("not json at all"), model="s"
    )
    assert events == []


def test_dedup_key_is_title_stable_across_time():
    # Same title, different casing/spacing → same key (so a reschedule re-arms
    # the same row rather than duplicating).
    assert _dedup_key("Call Mom") == _dedup_key("  call   mom ")
    assert _dedup_key("call mom") != _dedup_key("call dad")


def test_same_title_collapsed_within_round():
    reply = f'[{{"title": "sync", "when": "{_iso(1)}"}}, {{"title": "SYNC", "when": "{_iso(3)}"}}]'
    events = extract_definite_events(corpus="x", now=_NOW, provider=_FakeProvider(reply), model="s")
    assert len(events) == 1  # deduped by normalised title
