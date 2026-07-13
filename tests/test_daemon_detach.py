"""M113: `veles daemon start` detaches by default; --foreground keeps
the server attached to the current terminal."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

import pytest

from veles.cli.commands import daemon as daemon_cmd


@pytest.fixture()
def project(tmp_path, monkeypatch):
    """Init a real Veles project + force argparse defaults so
    `_resolve_active_project` finds it and `_ensure_api_key` shortcircuits.

    Resets the active-project / module-registry ContextVars on teardown
    so the foreground-path test doesn't leak into unrelated suites.
    """
    from veles.core.context import current_project, set_active_project
    from veles.core.modules import current_module_registry, set_module_registry
    from veles.core.project import init_project

    proj = init_project(tmp_path / "proj", name="detach-tests", force=False)
    monkeypatch.chdir(proj.root)
    # Snapshot pre-state so we can roll back after the test.
    prev_proj = current_project()
    prev_reg = current_module_registry()
    try:
        yield proj
    finally:
        set_active_project(prev_proj)
        set_module_registry(prev_reg)


def _start_args(**overrides) -> argparse.Namespace:
    base = dict(
        daemon_command="start",
        host="127.0.0.1",
        port=18877,
        foreground=False,
        provider="openrouter",
        model="anthropic/claude-sonnet-4.6",
        max_iterations=10,
        max_tokens=4096,
        verbose=False,
        no_compress=False,
        compress_threshold_tokens=50_000,
        compressor_model="anthropic/claude-haiku-4.5",
    )
    base.update(overrides)
    return argparse.Namespace(**base)


# ---- spawn_daemon now passes --foreground ----


def test_spawn_daemon_passes_foreground_flag(monkeypatch, tmp_path: Path) -> None:
    """The detached child receives `--foreground`, otherwise it would
    re-enter the detach branch and fork again forever."""
    from veles.daemon import spawn as spawn_mod

    captured: list[list[str]] = []

    class _FakePopen:
        pid = 4242

        def __init__(self, args, **kwargs):
            captured.append(args)

        def poll(self):
            return None

    monkeypatch.setattr(spawn_mod.subprocess, "Popen", _FakePopen)
    spawn_mod.spawn_daemon(project_root=tmp_path, host="127.0.0.1", port=8765)
    assert captured, "Popen was not called"
    args = captured[0]
    assert "--foreground" in args
    assert "daemon" in args and "start" in args


# ---- detach path ----


def test_detach_path_default_calls_spawn(
    project, isolated_user_home: Path, monkeypatch, capsys
) -> None:
    """No `--foreground` → `_cmd_daemon_start` delegates to
    `_detach_and_report`, which spawns + polls (pid file AND the child
    serving /v1/health with ITS pid — the 2026-07-09 fix) + returns 0."""
    import contextlib

    from tests.test_daemon_start_verify import _health_server
    from veles.daemon import spawn as spawn_mod

    web_run_calls: list[Any] = []
    monkeypatch.setattr("aiohttp.web.run_app", lambda *a, **k: web_run_calls.append((a, k)))

    pid_file = isolated_user_home / "daemon-detach-tests.pid"
    info_file = isolated_user_home / "daemon-detach-tests.info.json"
    fake_child_pid = 99_999_111  # very unlikely to clash with real pid

    # The success gate now requires the child to serve /v1/health with its
    # own pid; play the child's part with a stand-in health server.
    stack = contextlib.ExitStack()
    port = stack.enter_context(_health_server(pid=fake_child_pid))

    class _FakeProc:
        pid = fake_child_pid

        def poll(self):
            return None

    def fake_spawn(*, project_root, host, port, name=None, log_path=None):
        # Simulate the child writing its pid + info before we return.
        pid_file.write_text(f"{fake_child_pid}\n", encoding="utf-8")
        info_file.write_text(
            '{"host": "127.0.0.1", "port": 18877, '
            '"project_root": "/p", "project_name": "detach-tests", '
            f'"started_at": 1.0, "pid": {fake_child_pid}' + "}",
            encoding="utf-8",
        )
        return _FakeProc()

    monkeypatch.setattr(spawn_mod, "spawn_daemon", fake_spawn)
    # Pretend our fake child pid is alive (no actual process exists).
    # M153: `_detach_and_report` lives in (and resolves `_process_alive`
    # from) `daemon_lifecycle`, so patch the canonical module.
    from veles.cli.commands import daemon_lifecycle as lifecycle_mod

    monkeypatch.setattr(lifecycle_mod, "_process_alive", lambda pid: pid == fake_child_pid)
    monkeypatch.setattr("veles.cli._ensure_api_key", lambda provider, project=None: True)

    try:
        rc = daemon_cmd._cmd_daemon_start(_start_args(port=port))
    finally:
        stack.close()
    assert rc == 0
    assert web_run_calls == []  # parent didn't run the server
    out = capsys.readouterr().out
    assert "daemon started" in out
    assert "log:" in out
    # Cleanup pid file so other tests don't see a stale entry.
    pid_file.unlink(missing_ok=True)
    info_file.unlink(missing_ok=True)


def test_detach_path_spawn_returns_none_reports_failure(
    project, isolated_user_home: Path, monkeypatch, capsys
) -> None:
    from veles.daemon import spawn as spawn_mod

    monkeypatch.setattr(spawn_mod, "spawn_daemon", lambda **_: None)
    monkeypatch.setattr("veles.cli._ensure_api_key", lambda provider, project=None: True)

    rc = daemon_cmd._cmd_daemon_start(_start_args())
    assert rc == 1
    err = capsys.readouterr().err
    assert "failed to spawn" in err


def test_detach_path_pid_never_appears_reports_log_tail(
    project, isolated_user_home: Path, monkeypatch, capsys
) -> None:
    """Child exited before writing pid → parent times out and prints
    the tail of the daemon log file."""
    from veles.daemon import spawn as spawn_mod

    log_dir = isolated_user_home / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "daemon-detach-tests.log"
    log_file.write_text(
        "\n".join(f"line {i}: something went wrong" for i in range(25)) + "\n",
        encoding="utf-8",
    )

    class _DeadProc:
        pid = 12345

        def poll(self):
            return 1  # already exited

    monkeypatch.setattr(spawn_mod, "spawn_daemon", lambda **_: _DeadProc())
    monkeypatch.setattr("veles.cli._ensure_api_key", lambda provider, project=None: True)
    # Speed up the polling loop so the test doesn't take 5s.
    monkeypatch.setattr("time.sleep", lambda _s: None)

    rc = daemon_cmd._cmd_daemon_start(_start_args())
    assert rc == 1
    err = capsys.readouterr().err
    assert "did not start within 5s" in err
    assert "line 24" in err  # last of the 25 log lines


def test_detach_path_already_running_refuses(
    project, isolated_user_home: Path, monkeypatch, capsys
) -> None:
    """Existing pid file + live pid → reject the start (same project)."""
    pid_file = isolated_user_home / "daemon-detach-tests.pid"
    pid_file.write_text(f"{os.getpid()}\n", encoding="utf-8")
    monkeypatch.setattr("veles.cli._ensure_api_key", lambda provider, project=None: True)

    rc = daemon_cmd._cmd_daemon_start(_start_args())
    assert rc == 1
    err = capsys.readouterr().err
    assert "already running" in err
    pid_file.unlink(missing_ok=True)


# ---- --foreground path stays attached ----


def test_foreground_flag_runs_aiohttp_inline(
    project, isolated_user_home: Path, monkeypatch
) -> None:
    """With `--foreground`, the function skips `_detach_and_report`
    and calls `web.run_app` directly (we mock it so the test doesn't
    actually bind to a port)."""
    from veles.daemon import spawn as spawn_mod

    spawn_calls: list[Any] = []
    monkeypatch.setattr(spawn_mod, "spawn_daemon", lambda **k: spawn_calls.append(k))

    web_run_called: list[Any] = []
    monkeypatch.setattr("aiohttp.web.run_app", lambda *a, **k: web_run_called.append((a, k)))
    monkeypatch.setattr("veles.cli._ensure_api_key", lambda provider, project=None: True)

    rc = daemon_cmd._cmd_daemon_start(_start_args(foreground=True))
    assert rc == 0
    assert spawn_calls == []  # detach path skipped
    assert web_run_called, "web.run_app should have been called in foreground mode"
