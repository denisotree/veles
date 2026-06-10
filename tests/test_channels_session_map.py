"""M52 channels — SessionMap CRUD + persistence tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.channels.session_map import SessionMap, channel_session_path


@pytest.fixture()
def map_path(tmp_path: Path) -> Path:
    return tmp_path / "telegram-sessions.json"


def test_load_empty_when_file_missing(map_path: Path) -> None:
    m = SessionMap.load(map_path)
    assert m.list() == []
    assert m.get("anything") is None


def test_set_get_persists_atomically(map_path: Path) -> None:
    m = SessionMap.load(map_path)
    m.set("12345", "session-abc")
    assert map_path.is_file()
    assert m.get("12345") == "session-abc"

    reloaded = SessionMap.load(map_path)
    assert reloaded.get("12345") == "session-abc"


def test_set_updates_existing(map_path: Path) -> None:
    m = SessionMap.load(map_path)
    m.set("12345", "session-old")
    m.set("12345", "session-new")
    assert m.get("12345") == "session-new"


def test_reset_removes_entry(map_path: Path) -> None:
    m = SessionMap.load(map_path)
    m.set("12345", "session-abc")
    assert m.reset("12345") is True
    assert m.get("12345") is None
    assert m.reset("12345") is False


def test_list_sorted_by_last_used_desc(map_path: Path) -> None:
    m = SessionMap.load(map_path)
    m.set("a", "s-a")
    m.set("b", "s-b")
    m.set("c", "s-c")
    # most-recently-set first
    keys = [row[0] for row in m.list()]
    assert keys == ["c", "b", "a"]


def test_load_permissive_on_corrupt_json(map_path: Path) -> None:
    map_path.write_text("not json", encoding="utf-8")
    m = SessionMap.load(map_path)
    assert m.list() == []


def test_load_permissive_on_unexpected_shape(map_path: Path) -> None:
    map_path.write_text('{"sessions": "not-a-dict"}', encoding="utf-8")
    m = SessionMap.load(map_path)
    assert m.list() == []


def test_load_skips_invalid_entries(map_path: Path) -> None:
    map_path.write_text(
        '{"sessions": {"good": {"session_id": "ok", "last_used_at": 1}, '
        '"bad1": "not-a-dict", "bad2": {"no_session_id": true}}}',
        encoding="utf-8",
    )
    m = SessionMap.load(map_path)
    assert [row[0] for row in m.list()] == ["good"]


def test_channel_session_path_honors_veles_user_home(tmp_path: Path, monkeypatch) -> None:
    # VELES_USER_HOME replaces `~`, so state lands under `<override>/.veles/`
    # — unified with core.user_paths.user_home() in M158.
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "veles-home"))
    path = channel_session_path("telegram")
    assert path == tmp_path / "veles-home" / ".veles" / "channels" / "telegram-sessions.json"


def test_channel_session_path_uses_base_dir_override(tmp_path: Path) -> None:
    path = channel_session_path("slack", base_dir=tmp_path / "alt")
    assert path == tmp_path / "alt" / "slack-sessions.json"
