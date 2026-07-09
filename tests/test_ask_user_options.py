"""`ask_user` must coerce a stringified options list into a real list.

Weaker models frequently pass `options` as a JSON STRING —
`options='["Alpha", "Beta"]'` — instead of a list. The picker then iterates the
string character by character and renders one glyph per line (observed broken
render). Coerce so the picker always gets a proper list.
"""

from __future__ import annotations

import veles.core.tools.builtin.ask_user as m


def _capture(monkeypatch):
    seen: dict = {}
    monkeypatch.setattr(
        m, "ask_user_question", lambda q, opts: seen.__setitem__("opts", opts) or "answer"
    )
    return seen


def test_json_string_options_are_parsed_to_a_list(monkeypatch) -> None:
    seen = _capture(monkeypatch)
    m.ask_user("Pick?", options='["✅ Приступить", "Начать"]')
    assert seen["opts"] == ["✅ Приступить", "Начать"]


def test_list_options_pass_through(monkeypatch) -> None:
    seen = _capture(monkeypatch)
    m.ask_user("Pick?", options=["Alpha", "Beta"])
    assert seen["opts"] == ["Alpha", "Beta"]


def test_non_json_string_becomes_a_single_option(monkeypatch) -> None:
    seen = _capture(monkeypatch)
    m.ask_user("Pick?", options="just text")
    assert seen["opts"] == ["just text"]  # one option, never char-by-char


def test_none_and_empty_stay_none(monkeypatch) -> None:
    seen = _capture(monkeypatch)
    m.ask_user("Pick?", options=None)
    assert seen["opts"] is None
    m.ask_user("Pick?", options="[]")
    assert seen["opts"] is None
