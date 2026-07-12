"""M135-complete: live named-daemon-session lifecycle.

Covers the spawn/start/stop/status/restart `--name` plumbing on top of the
M135 named-session CRUD: per-instance pid paths, the `daemon_session=` resolver
wiring (so a named session boots on ITS OWN provider/model, not the project
default — the M125/M127/M130 mismatch class), child-side runtime_sessions
marking, and the require-a-declared-session guard. Real process spawning is
exercised by the manual smoke (`~/.tmp/veles-m135-smoke.sh`), not here.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from veles.core.project import init_project
from veles.core.project_config import load_project_config, save_project_config
from veles.core.runtime_sessions import RuntimeSessionStore


class _P:
    """Minimal project stand-in for path/store helpers (name + db path)."""

    def __init__(self, name: str, db: Path) -> None:
        self.name = name
        self.memory_db_path = db


class _Closeable:
    def close(self) -> None:
        pass


def test_cleanup_keeps_registry_entry_on_exit(tmp_path, monkeypatch):
    """Stop keeps, delete removes: `_cleanup_daemon_exit` must NOT drop the M97
    registry row on exit (so a stopped daemon stays visible, shown stopped) —
    only an explicit `daemon delete` / picker `d` removes it. The pid/info
    sidecars are still unlinked."""
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    from veles.cli.commands.daemon import _cleanup_daemon_exit
    from veles.daemon.registry import DaemonEntry, DaemonRegistry

    reg = DaemonRegistry()
    reg.upsert(
        DaemonEntry(
            slug="p",
            project_path=str(tmp_path / "p"),
            project_name="p",
            pid=999999,  # not a live pid → status_for() reads "stopped"
            host="127.0.0.1",
            port=8765,
            started_at=1.0,
        )
    )
    reg.save()

    pid_path = tmp_path / "daemon.pid"
    pid_path.write_text("1\n", encoding="utf-8")
    info_path = tmp_path / "daemon.info.json"
    info_path.write_text("{}", encoding="utf-8")

    _cleanup_daemon_exit(
        _P("p", tmp_path / "memory.db"),
        pid_path=pid_path,
        info_path=info_path,
        store=_Closeable(),
        jobs_store=_Closeable(),
        name=None,
    )

    assert DaemonRegistry.load().get("p") is not None  # entry REMAINS
    assert not pid_path.exists() and not info_path.exists()  # sidecars cleaned


# ---- resolver wiring (the highest-risk thread) ----


def test_factory_settings_uses_named_session_provider_and_model(tmp_path):
    from veles.cli.commands.daemon import _factory_settings_from_args

    project = init_project(tmp_path / "p", name="p")
    cfg = load_project_config(project)
    cfg.setdefault("engine", {})["provider"] = "openrouter"
    cfg["engine"]["model"] = "openrouter/base-model"
    cfg.setdefault("daemon", {})["api"] = {
        "provider": "ollama",
        "model": "ollama/qwen3:4b-instruct",
        "port": 8801,
    }
    save_project_config(project, cfg)

    args = argparse.Namespace(provider=None, model=None)
    pinned = _factory_settings_from_args(args, project, daemon_session="api")
    assert pinned.provider_name == "ollama"
    assert pinned.model == "ollama/qwen3:4b-instruct"

    # Without the session arg it falls back to the project [engine] base.
    base = _factory_settings_from_args(args, project)
    assert base.provider_name == "openrouter"
    assert base.model == "openrouter/base-model"


# ---- spawn re-exec ----


def test_spawn_daemon_passes_name(monkeypatch, tmp_path):
    import veles.daemon.spawn as spawn_mod

    captured: dict = {}

    class _FakePopen:
        def __init__(self, cmd, **kw):
            captured["cmd"] = cmd

    monkeypatch.setattr(spawn_mod.subprocess, "Popen", _FakePopen)
    spawn_mod.spawn_daemon(project_root=tmp_path, host="127.0.0.1", port=8801, name="api")
    cmd = captured["cmd"]
    assert "--foreground" in cmd
    assert "--name" in cmd
    assert cmd[cmd.index("--name") + 1] == "api"


def test_spawn_daemon_omits_name_when_none(monkeypatch, tmp_path):
    import veles.daemon.spawn as spawn_mod

    captured: dict = {}

    class _FakePopen:
        def __init__(self, cmd, **kw):
            captured["cmd"] = cmd

    monkeypatch.setattr(spawn_mod.subprocess, "Popen", _FakePopen)
    spawn_mod.spawn_daemon(project_root=tmp_path, host="127.0.0.1", port=8765)
    assert "--name" not in captured["cmd"]


# ---- per-instance paths ----


def test_resolve_instance_paths_named_vs_default(tmp_path, monkeypatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path))
    from veles.cli.commands.daemon import _resolve_instance_paths

    project = _P("myproj", tmp_path / "memory.db")
    pid_named, info_named = _resolve_instance_paths(project, "api")
    assert pid_named.name == "daemon-myproj-api.pid"
    assert info_named.name == "daemon-myproj-api.info.json"

    # M209: the unnamed daemon is per-project too — slug-keyed paths.
    pid_def, info_def = _resolve_instance_paths(project, None)
    assert pid_def.name == "daemon-myproj.pid"
    assert info_def.name == "daemon-myproj.info.json"


def test_instance_log_slug_matches_instance_log_path(tmp_path, monkeypatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path))
    from veles.cli.commands.daemon import _instance_log_slug, daemon_log_path
    from veles.daemon.paths import instance_log_path

    project = _P("myproj", tmp_path / "memory.db")
    slug = _instance_log_slug(project, "api")
    assert daemon_log_path(slug) == instance_log_path("myproj", "api")
    assert _instance_log_slug(project, None) == "myproj"


# ---- child-side store marking ----


def test_mark_session_running_and_stopped(tmp_path):
    from veles.cli.commands.daemon import _mark_session_running, _mark_session_stopped

    project = _P("myproj", tmp_path / "memory.db")
    store = RuntimeSessionStore(project.memory_db_path)
    store.create("api", "daemon", port=8801)
    store.close()

    _mark_session_running(project, "api", pid=4242)
    store = RuntimeSessionStore(project.memory_db_path)
    got = store.get_by_name("api", kind="daemon")
    assert got is not None and got.status == "running" and got.pid == 4242
    store.close()

    _mark_session_stopped(project, "api")
    store = RuntimeSessionStore(project.memory_db_path)
    got = store.get_by_name("api", kind="daemon")
    assert got is not None and got.status == "stopped" and got.pid is None
    store.close()


def test_mark_session_running_is_noop_when_unnamed(tmp_path):
    """The legacy daemon (name=None) has no runtime_sessions row — marking
    must be a no-op and never touch the DB."""
    from veles.cli.commands.daemon import _mark_session_running

    project = _P("myproj", tmp_path / "memory.db")
    _mark_session_running(project, None, pid=1)  # must not raise


# ---- require-declared-session guard ----


def test_start_named_session_without_row_errors(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "userhome"))
    from veles.cli.commands.daemon import _cmd_daemon_start

    project = init_project(tmp_path / "proj", name="proj")
    monkeypatch.chdir(project.root)

    args = argparse.Namespace(
        provider=None,
        model=None,
        host="127.0.0.1",
        port=8765,
        foreground=True,
        name="ghost",
    )
    rc = _cmd_daemon_start(args)
    assert rc == 2
    assert "ghost" in capsys.readouterr().err
