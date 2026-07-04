"""Persistent input history — load, append, navigate, draft anchor.

Path resolution is verified separately: every test writes into a path
under `tmp_path` (which is rooted at `./tmp/pytest/` via pyproject), so
nothing here touches the user's real `~/.veles/`.
"""

from __future__ import annotations

import json

from veles.cli.repl.history import InputHistory


def test_load_missing_file_returns_empty(tmp_path):
    h = InputHistory.load(tmp_path / "missing.jsonl")
    assert h.items == []
    assert not h.navigating


def test_append_writes_jsonl_line(tmp_path):
    path = tmp_path / "history.jsonl"
    h = InputHistory.load(path)
    h.append("hello world")
    assert path.is_file()
    line = path.read_text(encoding="utf-8").strip()
    assert json.loads(line) == {"text": "hello world"}


def test_append_dedupes_immediate_repeats(tmp_path):
    path = tmp_path / "history.jsonl"
    h = InputHistory.load(path)
    h.append("first")
    h.append("first")
    h.append("second")
    h.append("first")  # non-immediate dupe survives
    items = path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["text"] for line in items] == ["first", "second", "first"]


def test_previous_walks_back_in_order(tmp_path):
    h = InputHistory.load(tmp_path / "h.jsonl")
    for entry in ("a", "b", "c"):
        h.append(entry)
    h.start_navigation("draft")
    assert h.previous() == "c"
    assert h.previous() == "b"
    assert h.previous() == "a"
    # At oldest — stay put.
    assert h.previous() is None


def test_next_restores_draft_past_most_recent(tmp_path):
    h = InputHistory.load(tmp_path / "h.jsonl")
    for entry in ("a", "b"):
        h.append(entry)
    h.start_navigation("typing…")
    h.previous()  # → b
    h.previous()  # → a
    assert h.next() == "b"
    # Past the newest → restore draft, stop navigating.
    assert h.next() == "typing…"
    assert not h.navigating


def test_next_returns_none_when_not_navigating(tmp_path):
    h = InputHistory.load(tmp_path / "h.jsonl")
    h.append("a")
    # Without `previous()` first there is no nav cursor.
    assert h.next() is None


def test_reset_clears_cursor_and_draft(tmp_path):
    h = InputHistory.load(tmp_path / "h.jsonl")
    h.append("a")
    h.start_navigation("draft")
    h.previous()
    h.reset()
    assert not h.navigating


def test_persisted_history_round_trip(tmp_path):
    path = tmp_path / "h.jsonl"
    h1 = InputHistory.load(path)
    h1.append("alpha")
    h1.append("beta")
    h2 = InputHistory.load(path)
    assert h2.items == ["alpha", "beta"]


def test_load_tolerates_legacy_plain_lines(tmp_path):
    path = tmp_path / "h.jsonl"
    path.write_text('legacy line\n{"text": "jsonl line"}\n', encoding="utf-8")
    h = InputHistory.load(path)
    assert h.items == ["legacy line", "jsonl line"]


def test_append_skips_whitespace_only(tmp_path):
    h = InputHistory.load(tmp_path / "h.jsonl")
    h.append("   \n  ")
    assert h.items == []
