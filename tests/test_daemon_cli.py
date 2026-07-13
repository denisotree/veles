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

    def _fake_wizard(args, cwd):
        captured["called"] = True
        captured["suppress"] = getattr(args, "_suppress_wizard_daemon_autostart", None)
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

    def _fake_wizard(args, cwd):
        args._wizard_user_chose_no_project = True
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


def _project_here(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str = "p"):
    """Init a project and pin `_resolve_active_project` to it — stop/status
    address the cwd project's daemon since M209 (per-slug pid/info paths)."""
    import veles.cli as cli_mod
    from veles.core.project import init_project

    project = init_project(tmp_path, name=name)
    monkeypatch.setattr(cli_mod, "_resolve_active_project", lambda args: project)
    return project


def test_daemon_status_reports_not_running(
    isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    _project_here(monkeypatch, tmp_path)
    args = _ns(daemon_command="status")
    rc = daemon_cmd.cmd_daemon(args)
    assert rc == 1
    assert "not running" in capsys.readouterr().out


def test_daemon_status_outside_project_errors(
    isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """M209: stop/status are project-scoped; outside a project there is no
    daemon to address — point the user at the cross-project verbs instead."""
    import veles.cli as cli_mod

    monkeypatch.setattr(cli_mod, "_resolve_active_project", lambda args: None)
    args = _ns(daemon_command="status")
    rc = daemon_cmd.cmd_daemon(args)
    assert rc == 2
    assert "no Veles project" in capsys.readouterr().err


def test_daemon_status_reports_running_with_info(
    isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    _project_here(monkeypatch, tmp_path)
    pid_path = isolated_user_home / "daemon-p.pid"
    info_path = isolated_user_home / "daemon-p.info.json"
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


def test_daemon_status_cleans_up_stale_pid_marker(
    isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    _project_here(monkeypatch, tmp_path)
    pid_path = isolated_user_home / "daemon-p.pid"
    # Pick a definitely-dead pid (negative or improbable). Use pid 1 substitute:
    # the stable approach is to pick a very high pid we know isn't running.
    pid_path.write_text("999999\n", encoding="utf-8")
    args = _ns(daemon_command="status")
    rc = daemon_cmd.cmd_daemon(args)
    assert rc == 1
    assert "stale" in capsys.readouterr().out


def test_daemon_stop_no_pid_file(
    isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    _project_here(monkeypatch, tmp_path)
    args = _ns(daemon_command="stop")
    rc = daemon_cmd.cmd_daemon(args)
    assert rc == 1
    assert "no veles daemon pid file" in capsys.readouterr().err


def test_daemon_stop_stale_pid_cleans_up(
    isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    _project_here(monkeypatch, tmp_path)
    pid_path = isolated_user_home / "daemon-p.pid"
    info_path = isolated_user_home / "daemon-p.info.json"
    pid_path.write_text("999999\n", encoding="utf-8")
    info_path.write_text("{}", encoding="utf-8")
    args = _ns(daemon_command="stop")
    rc = daemon_cmd.cmd_daemon(args)
    assert rc == 0
    assert not pid_path.exists()
    assert not info_path.exists()


# ---------------- M209: per-project unnamed daemons ----------------


def test_unnamed_daemon_paths_are_per_project(tmp_path: Path, monkeypatch) -> None:
    """Two different projects must not share a pid lock — the second
    project's `daemon start` used to die on the first's global pid file."""
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path))
    from veles.cli.commands.daemon import _resolve_instance_paths

    proj_a = type("P", (), {"name": "alpha"})()
    proj_b = type("P", (), {"name": "beta"})()
    pid_a, info_a = _resolve_instance_paths(proj_a, None)
    pid_b, info_b = _resolve_instance_paths(proj_b, None)
    assert pid_a != pid_b
    assert info_a != info_b
    assert pid_a.name == "daemon-alpha.pid"
    assert pid_b.name == "daemon-beta.pid"


def test_second_project_start_not_blocked_by_first(isolated_user_home: Path, capsys) -> None:
    """`_write_pid_and_info` with a LIVE pid in project A's lock must not
    block project B (distinct slug), but must still block A itself."""
    from veles.cli.commands.daemon import _resolve_instance_paths, _write_pid_and_info

    proj_a = type("P", (), {"name": "alpha", "root": Path("/a")})()
    proj_b = type("P", (), {"name": "beta", "root": Path("/b")})()
    state = _ns(started_at=1.0)
    args = _ns(host="127.0.0.1", port=8765)

    pid_a, info_a = _resolve_instance_paths(proj_a, None)
    pid_a.write_text(f"{os.getpid()}\n", encoding="utf-8")  # A is "running"

    pid_b, info_b = _resolve_instance_paths(proj_b, None)
    assert _write_pid_and_info(state, args, proj_b, pid_path=pid_b, info_path=info_b) == 0

    capsys.readouterr()
    rc = _write_pid_and_info(state, args, proj_a, pid_path=pid_a, info_path=info_a)
    assert rc == 1
    assert "already running" in capsys.readouterr().err


def test_resolve_daemon_bind_picks_next_free_port(
    isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """M209: with no configured port, a busy 8765 rolls over to 8766 instead
    of colliding with another project's daemon."""
    import argparse

    from veles.core.project import init_project

    project = init_project(tmp_path, name="p")
    monkeypatch.setattr(daemon_cmd, "_port_is_free", lambda host, port: port != 8765)
    args = argparse.Namespace(host=None, port=None)
    daemon_cmd._resolve_daemon_bind(args, project, None)
    assert args.port == 8766


def _pinned_project(tmp_path: Path, port: int = 8799):
    from veles.core.project import init_project
    from veles.core.project_config import load_project_config, save_project_config

    project = init_project(tmp_path, name="p")
    cfg = load_project_config(project)
    cfg.setdefault("daemon", {})["port"] = port
    save_project_config(project, cfg)
    return project


def test_resolve_daemon_bind_config_port_pinned_when_occupant_unknown(
    isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A config-pinned port busy with something that is NOT a veles daemon
    (foreign service, dying predecessor) is used verbatim — the loud detach
    health-probe failure beats silently drifting off the pin."""
    import argparse

    project = _pinned_project(tmp_path)
    monkeypatch.setattr(daemon_cmd, "_port_is_free", lambda host, port: False)
    monkeypatch.setattr(daemon_cmd, "_veles_daemon_on_port", lambda host, port: None)
    args = argparse.Namespace(host=None, port=None)
    daemon_cmd._resolve_daemon_bind(args, project, None)
    assert args.port == 8799


def test_resolve_daemon_bind_config_port_rolls_off_other_projects_daemon(
    isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    """M211: the project wizard writes its default port (8765) into every
    project's config, so two wizard-made projects 'pin' the same port without
    the user choosing one. When the pinned port is held by ANOTHER project's
    veles daemon, roll to the next free port with a warning instead of
    crashing on bind."""
    import argparse

    project = _pinned_project(tmp_path)
    monkeypatch.setattr(daemon_cmd, "_port_is_free", lambda host, port: port != 8799)
    monkeypatch.setattr(
        daemon_cmd, "_veles_daemon_on_port", lambda host, port: ("other", "/somewhere/else")
    )
    args = argparse.Namespace(host=None, port=None)
    daemon_cmd._resolve_daemon_bind(args, project, None)
    assert args.port == 8800
    err = capsys.readouterr().err
    assert "already used by the daemon of project 'other'" in err
    assert "starting on 8800" in err


def test_resolve_daemon_bind_config_port_pinned_for_same_project(
    isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    """Our own daemon holding the pinned port is not a collision to roll away
    from — the pid-file check owns the 'already running' message."""
    import argparse

    project = _pinned_project(tmp_path)
    monkeypatch.setattr(daemon_cmd, "_port_is_free", lambda host, port: False)
    monkeypatch.setattr(
        daemon_cmd, "_veles_daemon_on_port", lambda host, port: ("p", str(project.root))
    )
    args = argparse.Namespace(host=None, port=None)
    daemon_cmd._resolve_daemon_bind(args, project, None)
    assert args.port == 8799
    assert "starting on" not in capsys.readouterr().err


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


def test_daemon_delete_unknown_returns_error(isolated_user_home: Path, capsys) -> None:
    args = _ns(daemon_command="delete", target="ghost", yes=True)
    rc = daemon_cmd.cmd_daemon(args)
    assert rc == 1
    assert "no daemon named 'ghost'" in capsys.readouterr().err


# ---- M212: daemon critical-ops confirmer ----


def test_daemon_critical_confirmer_fails_closed(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """M212: inside the daemon, `confirm_critical` must refuse WITHOUT
    prompting — even when stdin looks like a TTY — and log why. The default
    confirmer's input() froze the whole event loop when the detached child
    inherited the launcher's terminal."""
    import logging
    import sys as _sys

    from veles.cli.commands.daemon_lifecycle import _install_daemon_critical_confirmer
    from veles.core import critical_ops

    try:
        _install_daemon_critical_confirmer()
        monkeypatch.setattr(_sys.stdin, "isatty", lambda: True)

        def _boom(*_a: object) -> str:
            raise AssertionError("input() must not be called in the daemon")

        monkeypatch.setattr("builtins.input", _boom)
        with caplog.at_level(logging.WARNING, logger="veles.daemon"):
            ok = critical_ops.confirm_critical(
                "dispatch fetch_url", "possible prompt-injection exfiltration"
            )
        assert ok is False
        denials = [r for r in caplog.records if "auto-denied" in r.getMessage()]
        assert len(denials) == 1
        assert "possible prompt-injection exfiltration" in denials[0].getMessage()
    finally:
        critical_ops.set_critical_confirmer(None)


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

    import sys as _sys

    import veles.tui.screens.daemon_picker as picker_mod

    monkeypatch.setattr(_sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(_sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr(picker_mod, "DaemonPickerApp", _FakeApp)
    rc = daemon_cmd._cmd_daemon_picker(_ns())
    assert rc == 0
    assert captured["kwargs"].get("mouse") is False


def test_daemon_picker_non_tty_falls_back_to_list(
    isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """Bare `veles daemon` piped/redirected (non-TTY) must NOT launch the
    Textual picker — with no real terminal it hangs. Fall back to the plain
    daemon list. (Regression guard: the M197 revert dropped this guard;
    restored 2026-07-07.)"""
    import sys as _sys

    launched = {"picker": False}

    class _Boom:
        def __init__(self, *a, **k):
            launched["picker"] = True

        def run(self, *a, **k):
            launched["picker"] = True

    import veles.tui.screens.daemon_picker as picker_mod

    monkeypatch.setattr(_sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(_sys.stdout, "isatty", lambda: False)
    monkeypatch.setattr(picker_mod, "DaemonPickerApp", _Boom)
    rc = daemon_cmd._cmd_daemon_picker(_ns())
    assert launched["picker"] is False  # never launched Textual into a non-tty
    assert rc == 0


# ---------------- M173: host/port cascade + channel offer ----------------


def test_daemon_start_honours_config_port(
    isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The unnamed daemon must honour `[daemon] host/port` from config (what
    the project wizard writes) instead of always binding the argparse default.
    Cascade: explicit flag (None here) > config block > 127.0.0.1:8765."""
    import argparse

    import veles.cli as cli_mod
    from veles.core.project import init_project
    from veles.core.project_config import load_project_config, save_project_config

    monkeypatch.chdir(tmp_path)
    project = init_project(tmp_path, name="p")
    cfg = load_project_config(project)
    cfg.setdefault("daemon", {})
    cfg["daemon"]["host"] = "0.0.0.0"
    cfg["daemon"]["port"] = 8799
    save_project_config(project, cfg)

    monkeypatch.setattr(cli_mod, "_resolve_active_project", lambda args: project)
    monkeypatch.setattr(cli_mod, "_ensure_api_key", lambda *a, **k: True)
    captured: dict[str, object] = {}

    def _fake_detach(args, project, *, name=None):
        captured["host"] = args.host
        captured["port"] = args.port
        return 0

    monkeypatch.setattr(daemon_cmd, "_detach_and_report", _fake_detach)

    args = argparse.Namespace(
        command="daemon",
        foreground=False,
        host=None,
        port=None,
        provider="ollama",
        model=None,
        name=None,
        no_wizard=True,
    )
    rc = daemon_cmd._cmd_daemon_start(args)
    assert rc == 0
    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 8799


def test_daemon_start_explicit_port_beats_config(
    isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An explicit `--port` outranks the config block."""
    import argparse

    import veles.cli as cli_mod
    from veles.core.project import init_project
    from veles.core.project_config import load_project_config, save_project_config

    monkeypatch.chdir(tmp_path)
    project = init_project(tmp_path, name="p")
    cfg = load_project_config(project)
    cfg.setdefault("daemon", {})["port"] = 8799
    save_project_config(project, cfg)

    monkeypatch.setattr(cli_mod, "_resolve_active_project", lambda args: project)
    monkeypatch.setattr(cli_mod, "_ensure_api_key", lambda *a, **k: True)
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        daemon_cmd,
        "_detach_and_report",
        lambda args, project, *, name=None: captured.update(port=args.port) or 0,
    )

    args = argparse.Namespace(
        command="daemon",
        foreground=False,
        host=None,
        port=9001,  # explicit
        provider="ollama",
        model=None,
        name=None,
        no_wizard=True,
    )
    assert daemon_cmd._cmd_daemon_start(args) == 0
    assert captured["port"] == 9001


def test_resolve_daemon_bind_defaults_when_no_config(
    isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import argparse

    from veles.core.project import init_project

    project = init_project(tmp_path, name="p")
    # Pin the probe: the real 8765 may be busy on a dev machine running an
    # actual daemon, which would flake this into asserting 8766.
    monkeypatch.setattr(daemon_cmd, "_port_is_free", lambda host, port: True)
    args = argparse.Namespace(host=None, port=None)
    daemon_cmd._resolve_daemon_bind(args, project, None)
    assert args.host == "127.0.0.1"
    assert args.port == 8765


def _interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys as _sys

    monkeypatch.setattr(_sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(_sys.stdout, "isatty", lambda: True)


def _force_stdin_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the Textual path unavailable so the legacy stdin flow runs."""
    import veles.tui.wizard.daemon_runner as dr

    def _boom(*_a, **_k):
        raise RuntimeError("no TUI in tests")

    monkeypatch.setattr(dr, "run_daemon_start_wizard_tui", _boom)


def test_start_wizard_prefers_tui_and_applies_bind(
    isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Live 2026-07-09: an interactive `veles daemon start` with no channel
    configured must run the Textual start wizard (bind + channel steps), not
    a bare stdin [y/N] prompt — and the host/port the user picked must apply
    to THIS launch."""
    import veles.tui.wizard.daemon_runner as dr
    from veles.core.project import init_project

    project = init_project(tmp_path, name="p")
    _interactive(monkeypatch)
    seen: dict[str, object] = {}

    def _fake_tui(project_, *, session, host, port):
        seen.update(session=session, host=host, port=port)
        return {"daemon_bind": {"host": "0.0.0.0", "port": 9100}, "channel": None}

    monkeypatch.setattr(dr, "run_daemon_start_wizard_tui", _fake_tui)
    args = _ns(no_wizard=False, host="127.0.0.1", port=8765)
    daemon_cmd._maybe_run_start_wizard(args, project, session=None)
    assert seen == {"session": None, "host": "127.0.0.1", "port": 8765}
    assert args.host == "0.0.0.0"
    assert args.port == 9100


def test_start_wizard_tui_cancel_keeps_args(
    isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ctrl+Q in the wizard = start with what we already have, not abort."""
    import veles.cli.channel_wizard as cw
    import veles.tui.wizard.daemon_runner as dr
    from veles.core.project import init_project

    project = init_project(tmp_path, name="p")
    _interactive(monkeypatch)
    monkeypatch.setattr(dr, "run_daemon_start_wizard_tui", lambda *a, **k: None)
    calls: dict[str, object] = {}
    monkeypatch.setattr(cw, "add_channel", lambda *a, **k: calls.update(called=True))
    args = _ns(no_wizard=False, host="127.0.0.1", port=8765)
    daemon_cmd._maybe_run_start_wizard(args, project, session=None)
    assert args.host == "127.0.0.1" and args.port == 8765
    assert calls.get("called") is None  # no stdin fallback after a real TUI run


def test_start_wizard_falls_back_to_stdin_when_accepted(
    isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import veles.cli.channel_wizard as cw
    import veles.cli.project_wizard as pw
    from veles.core.project import init_project

    project = init_project(tmp_path, name="p")
    _interactive(monkeypatch)
    _force_stdin_fallback(monkeypatch)
    monkeypatch.setattr(pw, "_ask_yes_no", lambda *a, **k: True)
    calls: dict[str, object] = {}
    monkeypatch.setattr(
        cw,
        "add_channel",
        lambda project, *, session=None: calls.update(called=True, session=session),
    )

    daemon_cmd._maybe_run_start_wizard(_ns(no_wizard=False), project, session=None)
    assert calls.get("called") is True
    assert calls.get("session") is None


def test_start_wizard_skips_when_channel_exists(
    isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import veles.cli.channel_wizard as cw
    import veles.tui.wizard.daemon_runner as dr
    from veles.cli.channel_wizard import apply_channel
    from veles.core.project import init_project

    project = init_project(tmp_path, name="p")
    apply_channel(
        project, session=None, channel="telegram", secrets={"bot_token": "t"}, config_fields={}
    )
    _interactive(monkeypatch)
    calls: dict[str, object] = {}
    monkeypatch.setattr(cw, "add_channel", lambda *a, **k: calls.update(called=True))
    monkeypatch.setattr(
        dr, "run_daemon_start_wizard_tui", lambda *a, **k: calls.update(called=True)
    )

    daemon_cmd._maybe_run_start_wizard(_ns(no_wizard=False), project, session=None)
    assert calls.get("called") is None  # a channel already exists → no wizard at all


def test_start_wizard_stdin_fallback_skips_when_declined(
    isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import veles.cli.channel_wizard as cw
    import veles.cli.project_wizard as pw
    from veles.core.project import init_project

    project = init_project(tmp_path, name="p")
    _interactive(monkeypatch)
    _force_stdin_fallback(monkeypatch)
    monkeypatch.setattr(pw, "_ask_yes_no", lambda *a, **k: False)
    calls: dict[str, object] = {}
    monkeypatch.setattr(cw, "add_channel", lambda *a, **k: calls.update(called=True))

    daemon_cmd._maybe_run_start_wizard(_ns(no_wizard=False), project, session=None)
    assert calls.get("called") is None


def test_start_wizard_skips_when_no_wizard(
    isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import veles.cli.channel_wizard as cw
    from veles.core.project import init_project

    project = init_project(tmp_path, name="p")
    _interactive(monkeypatch)
    calls: dict[str, object] = {}
    monkeypatch.setattr(cw, "add_channel", lambda *a, **k: calls.update(called=True))

    daemon_cmd._maybe_run_start_wizard(_ns(no_wizard=True), project, session=None)
    assert calls.get("called") is None
