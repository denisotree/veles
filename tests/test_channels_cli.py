"""M52 channels — CLI verb tests (no real network)."""

from __future__ import annotations

from pathlib import Path

from veles.cli.commands import channel as channel_cmd
from veles.core.chat_sessions import SessionMap, channel_session_path

# `isolated_user_home` comes from tests/conftest.py.


def _ns(**fields):
    return type("A", (), fields)()


def test_channel_run_requires_bot_token(isolated_user_home: Path, capsys, monkeypatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    args = _ns(
        channel_command="run",
        channel="telegram",
        secret=None,
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
        secret="bot-xyz",
        daemon_url=None,
        daemon_token=None,
    )
    rc = channel_cmd.cmd_channel(args)
    assert rc == 2
    err = capsys.readouterr().err
    assert "VELES_DAEMON_TOKEN" in err


def test_channel_run_reads_a_daemon_token_stored_with_veles_secret(
    isolated_user_home: Path, capsys, monkeypatch, fake_keyring
) -> None:
    """M271: the token was read from the environment only, so one stored with
    `veles secret set` was never used. Stored through the real CLI here; the
    run then fails *later* (unknown channel), which proves the token check passed."""
    from veles.cli import main as cli_main

    monkeypatch.delenv("VELES_DAEMON_TOKEN", raising=False)
    assert cli_main(["secret", "set", "VELES_DAEMON_TOKEN", "vd_from_keychain"]) == 0
    capsys.readouterr()
    args = _ns(
        channel_command="run",
        channel="no-such-channel",
        secret="bot-xyz",
        daemon_url=None,
        daemon_token=None,
    )
    channel_cmd.cmd_channel(args)
    err = capsys.readouterr().err
    assert "VELES_DAEMON_TOKEN is required" not in err
    assert "no-such-channel" in err


def test_channel_run_refuses_unknown_channel(isolated_user_home: Path, capsys, monkeypatch) -> None:
    args = _ns(
        channel_command="run",
        channel="slack",
        secret="x",
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


def test_channel_list_sees_a_user_module_platform(
    isolated_user_home: Path, tmp_path: Path, monkeypatch, capsys
) -> None:
    """`veles channel` needs no project — it must still load the user's modules,
    or a platform installed from the registry is invisible to it."""
    from veles.cli import main
    from veles.core.registry.gate import approve_module
    from veles.core.user_paths import user_modules_dir

    mod = user_modules_dir() / "fakech"
    mod.mkdir(parents=True)
    (mod / "module.toml").write_text(
        '[module]\nname = "fakech"\ndescription = "d"\nentrypoint = "e.py:register"\n',
        encoding="utf-8",
    )
    source = Path(__file__).parent / "channels" / "fake_platform.py"
    (mod / "e.py").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    approve_module(mod, name="fakech", project_root=None)
    monkeypatch.chdir(tmp_path)
    assert main(["channel", "list"]) == 0
    assert "fake" in capsys.readouterr().out


def test_channel_run_without_a_channel_names_the_choices(
    isolated_user_home: Path, capsys, fake_platform
) -> None:
    args = _ns(channel_command="run", channel=None, secret=None, daemon_url=None, daemon_token="t")
    assert channel_cmd.cmd_channel(args) == 2
    err = capsys.readouterr().err
    assert "fake" in err and "telegram" in err and "--channel" in err


def test_channel_unknown_subcommand(isolated_user_home: Path, capsys) -> None:
    args = _ns(channel_command="nope")
    rc = channel_cmd.cmd_channel(args)
    assert rc == 2
    assert "unknown channel subcommand" in capsys.readouterr().err
