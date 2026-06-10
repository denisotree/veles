"""M74 — SessionSource dataclass and key generation."""

from __future__ import annotations

from veles.channels.session_map import SessionMap, SessionSource


def test_key_without_thread():
    src = SessionSource(platform="telegram", chat_id="42")
    assert src.key() == "telegram:42"


def test_key_with_thread():
    src = SessionSource(platform="slack", chat_id="C01", thread_id="1700.000")
    assert src.key() == "slack:C01:1700.000"


def test_key_ignores_guild_and_user():
    src = SessionSource(
        platform="discord",
        chat_id="channel-1",
        user_id="user-7",
        guild_id="guild-3",
    )
    assert src.key() == "discord:channel-1"


def test_label_matches_key():
    src = SessionSource(platform="telegram", chat_id="42", thread_id="t1")
    assert src.label() == "telegram:42:t1"


def test_round_trip_via_session_map(tmp_path):
    path = tmp_path / "telegram-sessions.json"
    src = SessionSource(platform="telegram", chat_id="42")
    m = SessionMap.load(path)
    m.set(src.key(), "ses-abc")

    reloaded = SessionMap.load(path)
    assert reloaded.get(src.key()) == "ses-abc"


def test_thread_keys_are_distinct(tmp_path):
    path = tmp_path / "slack-sessions.json"
    main = SessionSource(platform="slack", chat_id="C01")
    thread = SessionSource(platform="slack", chat_id="C01", thread_id="t1")
    m = SessionMap.load(path)
    m.set(main.key(), "ses-main")
    m.set(thread.key(), "ses-thread")
    assert m.get(main.key()) == "ses-main"
    assert m.get(thread.key()) == "ses-thread"
