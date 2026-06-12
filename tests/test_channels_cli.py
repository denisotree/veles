"""M52 channels — CLI verb tests (no real network)."""

from __future__ import annotations

from pathlib import Path

from veles.channels.session_map import SessionMap, channel_session_path
from veles.cli.commands import channel as channel_cmd

# `isolated_user_home` comes from tests/conftest.py.


def _ns(**fields):
    return type("A", (), fields)()


def test_channel_run_requires_bot_token(isolated_user_home: Path, capsys, monkeypatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    args = _ns(
        channel_command="run",
        channel="telegram",
        bot_token=None,
        daemon_url=None,
        daemon_token="vd_x",
    )
    rc = channel_cmd.cmd_channel(args)
    assert rc == 2
    err = capsys.readouterr().err
    assert "TELEGRAM_BOT_TOKEN" in err


def test_channel_run_requires_daemon_token(isolated_user_home: Path, capsys, monkeypatch) -> None:
    monkeypatch.delenv("VELES_DAEMON_TOKEN", raising=False)
    args = _ns(
        channel_command="run",
        channel="telegram",
        bot_token="bot-xyz",
        daemon_url=None,
        daemon_token=None,
    )
    rc = channel_cmd.cmd_channel(args)
    assert rc == 2
    err = capsys.readouterr().err
    assert "VELES_DAEMON_TOKEN" in err


def test_channel_run_refuses_unknown_channel(isolated_user_home: Path, capsys, monkeypatch) -> None:
    args = _ns(
        channel_command="run",
        channel="slack",
        bot_token="x",
        daemon_url=None,
        daemon_token="vd_x",
    )
    rc = channel_cmd.cmd_channel(args)
    assert rc == 2
    err = capsys.readouterr().err
    # M65: error message comes from PlatformRegistry.get_platform — names
    # the unknown channel and the registered alternatives.
    assert "slack" in err
    assert "telegram" in err


def test_channel_list_sessions_empty(isolated_user_home: Path, capsys) -> None:
    args = _ns(channel_command="list-sessions", channel="telegram")
    rc = channel_cmd.cmd_channel(args)
    assert rc == 0
    assert "no sessions" in capsys.readouterr().out


def test_channel_list_sessions_shows_entries(isolated_user_home: Path, capsys) -> None:
    sm = SessionMap.load(channel_session_path("telegram"))
    sm.set("12345", "ses-abc")
    args = _ns(channel_command="list-sessions", channel="telegram")
    rc = channel_cmd.cmd_channel(args)
    assert rc == 0
    out = capsys.readouterr().out
    assert "12345" in out
    assert "ses-abc" in out


def test_channel_reset_session_removes_mapping(isolated_user_home: Path, capsys) -> None:
    sm = SessionMap.load(channel_session_path("telegram"))
    sm.set("12345", "ses-abc")
    args = _ns(channel_command="reset-session", channel="telegram", chat_id="12345")
    rc = channel_cmd.cmd_channel(args)
    assert rc == 0
    assert "forgot" in capsys.readouterr().out
    reloaded = SessionMap.load(channel_session_path("telegram"))
    assert reloaded.get("12345") is None


def test_channel_reset_session_missing(isolated_user_home: Path, capsys) -> None:
    args = _ns(channel_command="reset-session", channel="telegram", chat_id="999")
    rc = channel_cmd.cmd_channel(args)
    assert rc == 1
    assert "no session" in capsys.readouterr().err


def test_channel_unknown_subcommand(isolated_user_home: Path, capsys) -> None:
    args = _ns(channel_command="nope")
    rc = channel_cmd.cmd_channel(args)
    assert rc == 2
    assert "unknown channel subcommand" in capsys.readouterr().err
