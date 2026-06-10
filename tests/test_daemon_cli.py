"""M51 daemon — CLI verb tests (token + status without starting a real server)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from veles.cli.commands import daemon as daemon_cmd
from veles.daemon.auth import TokenStore


# `isolated_user_home` comes from tests/conftest.py (yields the
# `<home>/.veles/` dir where daemon.pid / daemon.tokens.json land).


def _ns(**fields):
    return type("A", (), fields)()


# ---------------- M129: `veles daemon start` bootstraps a missing project ----------------


def test_daemon_start_runs_wizard_when_no_project(
    isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    """`daemon` is dispatched before main()'s generic wizard path, so
    `veles daemon start` used to dead-end on an uninitialised dir. M129:
    it now runs the project wizard (with its own daemon-autostart
    suppressed). Here the wizard declines → falls through to the error."""
    import argparse

    import veles.cli as cli_mod
    import veles.cli.project_wizard as pw_mod

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli_mod, "_resolve_active_project", lambda args: None)

    captured: dict[str, object] = {}

    def _fake_wizard(args, cwd):  # noqa: ANN001, ANN202
        captured["called"] = True
        captured["suppress"] = getattr(
            args, "_suppress_wizard_daemon_autostart", None
        )
        return None

    monkeypatch.setattr(pw_mod, "maybe_run_project_wizard", _fake_wizard)

    args = argparse.Namespace(
        command="daemon",
        foreground=False,
        host="127.0.0.1",
        port=8765,
        provider="openrouter",
    )
    rc = daemon_cmd._cmd_daemon_start(args)

    assert captured.get("called") is True
    assert captured.get("suppress") is True
    assert rc == 2  # wizard returned None → standard no-project error
    assert "no Veles project found" in capsys.readouterr().err


def test_daemon_start_clean_decline_exits_zero(
    isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    """When the wizard runs and the user consciously declines to init a
    project (mirrors main()'s `_wizard_user_chose_no_project`), exit 0
    rather than the generic error."""
    import argparse

    import veles.cli as cli_mod
    import veles.cli.project_wizard as pw_mod

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli_mod, "_resolve_active_project", lambda args: None)

    def _fake_wizard(args, cwd):  # noqa: ANN001, ANN202
        args._wizard_user_chose_no_project = True  # noqa: SLF001
        return None

    monkeypatch.setattr(pw_mod, "maybe_run_project_wizard", _fake_wizard)

    args = argparse.Namespace(
        command="daemon",
        foreground=False,
        host="127.0.0.1",
        port=8765,
        provider="openrouter",
    )
    rc = daemon_cmd._cmd_daemon_start(args)
    assert rc == 0
    assert "nothing to do" in capsys.readouterr().err


def test_daemon_token_add_creates_token_file(isolated_user_home: Path, capsys) -> None:
    args = _ns(daemon_command="token", daemon_token_command="add", name="tui")
    rc = daemon_cmd.cmd_daemon(args)
    assert rc == 0
    captured = capsys.readouterr()
    assert "vd_" in captured.out

    store = TokenStore.load(isolated_user_home / "daemon.tokens.json")
    assert [e.name for e in store.list()] == ["tui"]


def test_daemon_token_add_refuses_duplicate(isolated_user_home: Path, capsys) -> None:
    args = _ns(daemon_command="token", daemon_token_command="add", name="tui")
    daemon_cmd.cmd_daemon(args)
    capsys.readouterr()
    rc = daemon_cmd.cmd_daemon(args)
    assert rc == 1
    err = capsys.readouterr().err
    assert "already exists" in err


def test_daemon_token_list_shows_masked(isolated_user_home: Path, capsys) -> None:
    store = TokenStore.load(isolated_user_home / "daemon.tokens.json")
    entry = store.add("tui")
    args = _ns(daemon_command="token", daemon_token_command="list")
    rc = daemon_cmd.cmd_daemon(args)
    assert rc == 0
    out = capsys.readouterr().out
    assert "tui" in out
    # masked: full token must NOT appear
    assert entry.token not in out
    assert entry.token[:6] in out


def test_daemon_token_list_empty(isolated_user_home: Path, capsys) -> None:
    args = _ns(daemon_command="token", daemon_token_command="list")
    rc = daemon_cmd.cmd_daemon(args)
    assert rc == 0
    assert "no tokens" in capsys.readouterr().out


def test_daemon_token_remove(isolated_user_home: Path, capsys) -> None:
    store = TokenStore.load(isolated_user_home / "daemon.tokens.json")
    store.add("tui")
    args = _ns(daemon_command="token", daemon_token_command="remove", name="tui")
    rc = daemon_cmd.cmd_daemon(args)
    assert rc == 0
    assert "removed" in capsys.readouterr().out
    reloaded = TokenStore.load(isolated_user_home / "daemon.tokens.json")
    assert reloaded.list() == []


def test_daemon_token_remove_missing(isolated_user_home: Path, capsys) -> None:
    args = _ns(daemon_command="token", daemon_token_command="remove", name="ghost")
    rc = daemon_cmd.cmd_daemon(args)
    assert rc == 1
    assert "no token named" in capsys.readouterr().err


def test_daemon_status_reports_not_running(isolated_user_home: Path, capsys) -> None:
    args = _ns(daemon_command="status")
    rc = daemon_cmd.cmd_daemon(args)
    assert rc == 1
    assert "not running" in capsys.readouterr().out


def test_daemon_status_reports_running_with_info(isolated_user_home: Path, capsys) -> None:
    pid_path = isolated_user_home / "daemon.pid"
    info_path = isolated_user_home / "daemon.info.json"
    pid_path.write_text(f"{os.getpid()}\n", encoding="utf-8")
    info_path.write_text(
        '{"host":"127.0.0.1","port":8765,"project_name":"demo",'
        '"project_root":"/tmp/demo","started_at":1700000000.0,"pid":' + str(os.getpid()) + "}",
        encoding="utf-8",
    )
    args = _ns(daemon_command="status")
    rc = daemon_cmd.cmd_daemon(args)
    assert rc == 0
    out = capsys.readouterr().out
    assert "running" in out
    assert "127.0.0.1:8765" in out
    assert "demo" in out


def test_daemon_status_cleans_up_stale_pid_marker(isolated_user_home: Path, capsys) -> None:
    pid_path = isolated_user_home / "daemon.pid"
    # Pick a definitely-dead pid (negative or improbable). Use pid 1 substitute:
    # the stable approach is to pick a very high pid we know isn't running.
    pid_path.write_text("999999\n", encoding="utf-8")
    args = _ns(daemon_command="status")
    rc = daemon_cmd.cmd_daemon(args)
    assert rc == 1
    assert "stale" in capsys.readouterr().out


def test_daemon_stop_no_pid_file(isolated_user_home: Path, capsys) -> None:
    args = _ns(daemon_command="stop")
    rc = daemon_cmd.cmd_daemon(args)
    assert rc == 1
    assert "no veles daemon pid file" in capsys.readouterr().err


def test_daemon_stop_stale_pid_cleans_up(isolated_user_home: Path, capsys) -> None:
    pid_path = isolated_user_home / "daemon.pid"
    info_path = isolated_user_home / "daemon.info.json"
    pid_path.write_text("999999\n", encoding="utf-8")
    info_path.write_text("{}", encoding="utf-8")
    args = _ns(daemon_command="stop")
    rc = daemon_cmd.cmd_daemon(args)
    assert rc == 0
    assert not pid_path.exists()
    assert not info_path.exists()


# ---- delete confirmation + --yes (C) ----


def _seed_dead_daemon_entry(isolated_user_home: Path, slug: str = "demo") -> Path:
    """Write a registry entry whose pid is definitely not running so
    `is_alive` returns False and no actual process gets signalled."""
    from veles.daemon.registry import DaemonEntry, DaemonRegistry

    reg = DaemonRegistry.load()
    reg.entries[slug] = DaemonEntry(
        slug=slug,
        project_path="/tmp/whatever",
        project_name=slug,
        pid=999999,
        host="127.0.0.1",
        port=8765,
        started_at=0.0,
    )
    reg.save()
    return isolated_user_home / "daemons.json"


def test_daemon_delete_aborts_on_n_response(
    isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """Bare `delete demo` asks for confirmation; `n` keeps the daemon."""
    _seed_dead_daemon_entry(isolated_user_home, "demo")
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")
    args = _ns(daemon_command="delete", target="demo", yes=False)
    rc = daemon_cmd.cmd_daemon(args)
    assert rc == 0
    assert "aborted" in capsys.readouterr().out
    # Entry still in registry.
    from veles.daemon.registry import DaemonRegistry

    assert DaemonRegistry.load().get("demo") is not None


def test_daemon_delete_proceeds_on_y_response(
    isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    _seed_dead_daemon_entry(isolated_user_home, "demo")
    monkeypatch.setattr("builtins.input", lambda _prompt: "y")
    args = _ns(daemon_command="delete", target="demo", yes=False)
    rc = daemon_cmd.cmd_daemon(args)
    assert rc == 0
    assert "deleted daemon 'demo'" in capsys.readouterr().out
    from veles.daemon.registry import DaemonRegistry

    assert DaemonRegistry.load().get("demo") is None


def test_daemon_delete_yes_flag_skips_prompt(
    isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """`--yes` must not call input() — protects scripts from hanging
    on a stale TTY."""
    _seed_dead_daemon_entry(isolated_user_home, "demo")

    def _boom(_prompt: str) -> str:
        raise AssertionError("input() must not be invoked when --yes is set")

    monkeypatch.setattr("builtins.input", _boom)
    args = _ns(daemon_command="delete", target="demo", yes=True)
    rc = daemon_cmd.cmd_daemon(args)
    assert rc == 0
    from veles.daemon.registry import DaemonRegistry

    assert DaemonRegistry.load().get("demo") is None


def test_daemon_delete_unknown_returns_error(
    isolated_user_home: Path, capsys
) -> None:
    args = _ns(daemon_command="delete", target="ghost", yes=True)
    rc = daemon_cmd.cmd_daemon(args)
    assert rc == 1
    assert "no daemon named 'ghost'" in capsys.readouterr().err


# ---- _graceful_stop helper ----


def test_graceful_stop_returns_true_when_pid_already_dead(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No-op when the process already exited between start and the
    SIGTERM call — graceful_stop returns True without an error."""
    from veles.cli.commands.daemon import _graceful_stop

    def _raise_not_found(_pid: int, _sig: int) -> None:
        raise ProcessLookupError

    monkeypatch.setattr("os.kill", _raise_not_found)
    assert _graceful_stop(999999, timeout=0.1) is True


def test_graceful_stop_escalates_to_sigkill_after_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SIGTERM sent → process keeps running → SIGKILL must follow."""
    import signal as _signal

    from veles.cli.commands.daemon import _graceful_stop

    signals: list[int] = []

    def _record(_pid: int, sig: int) -> None:
        signals.append(sig)

    # First poll: alive; after SIGKILL: dead. Mock `is_alive` per-call.
    state = {"calls": 0}

    def _is_alive(_pid: int) -> bool:
        state["calls"] += 1
        # Stay alive through all SIGTERM polls; die only after SIGKILL.
        return _signal.SIGKILL not in signals

    monkeypatch.setattr("os.kill", _record)
    monkeypatch.setattr("veles.daemon.registry.is_alive", _is_alive)
    ok = _graceful_stop(999999, timeout=0.1)
    assert ok is True
    assert _signal.SIGTERM in signals
    assert _signal.SIGKILL in signals


def test_daemon_picker_runs_with_mouse_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The bare `veles daemon` picker must launch Textual with
    `mouse=False` so the terminal handles native text selection +
    the system clipboard shortcut (regression guard for the M115.x
    selection policy applied to the daemon picker)."""
    captured: dict[str, object] = {}

    class _FakeApp:
        def __init__(self, *args, **kwargs):
            captured["init_kwargs"] = kwargs

        def run(self, *args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs

    import veles.tui.screens.daemon_picker as picker_mod

    monkeypatch.setattr(picker_mod, "DaemonPickerApp", _FakeApp)
    rc = daemon_cmd._cmd_daemon_picker(_ns())
    assert rc == 0
    assert captured["kwargs"].get("mouse") is False
