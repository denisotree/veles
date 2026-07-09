"""Live 2026-07-09: a detached `veles daemon start` child crashed right after
its pid file appeared (port still held by a dying predecessor) — the parent
had already printed "daemon started (pid …)" and the child's traceback went
to /dev/null, leaving a registry entry pointing at a corpse and zero evidence
in the daemon log.

Three guarantees under test:
1. `_detach_and_report` declares success only once the child actually LISTENS
   on the bind port; a child that never serves (or dies while coming up) is a
   loud failure with the log tail.
2. `spawn_daemon` routes the child's stdout/stderr into the daemon log file
   instead of /dev/null, so early crashes leave a trace.
3. `_run_app_logged` writes the crash traceback to the `veles.daemon` logger
   before re-raising, so even logging-visible failures land in the log.
"""

from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from veles.cli.commands import daemon_lifecycle as dl
from veles.core.project import init_project


@pytest.fixture(autouse=True)
def _isolated_user_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("VELES_USER_HOME", str(home))
    return home


@pytest.fixture
def project(tmp_path: Path):
    return init_project(tmp_path / "proj", name="proj")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _fake_child() -> subprocess.Popen:
    """A real process that stays alive (like the doomed daemon child did)
    but never listens on anything."""
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])


def _spawn_stub(child: subprocess.Popen, pid_path: Path):
    """spawn_daemon stand-in: 'child' comes up far enough to write its pid
    file, then keeps running without serving."""

    def _spawn(*, project_root, host, port, name=None, log_path=None):
        pid_path.parent.mkdir(parents=True, exist_ok=True)
        pid_path.write_text(f"{child.pid}\n", encoding="utf-8")
        return child

    return _spawn


def test_detach_report_fails_when_child_never_listens(
    project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    child = _fake_child()
    try:
        pid_path, _info = dl._resolve_instance_paths(project, None)
        monkeypatch.setattr("veles.daemon.spawn.spawn_daemon", _spawn_stub(child, pid_path))
        args = argparse.Namespace(host="127.0.0.1", port=_free_port())
        rc = dl._detach_and_report(args, project, timeout=1.5)
        assert rc == 1
        err = capsys.readouterr().err
        assert "not serving" in err or "did not start" in err
    finally:
        child.terminate()
        child.wait(timeout=5)


def test_detach_report_succeeds_when_port_listens(
    project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    child = _fake_child()
    listener = socket.socket()
    try:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        pid_path, _info = dl._resolve_instance_paths(project, None)
        monkeypatch.setattr("veles.daemon.spawn.spawn_daemon", _spawn_stub(child, pid_path))
        args = argparse.Namespace(host="127.0.0.1", port=port)
        rc = dl._detach_and_report(args, project, timeout=5.0)
        assert rc == 0
        assert "daemon started" in capsys.readouterr().out
    finally:
        listener.close()
        child.terminate()
        child.wait(timeout=5)


def test_detach_report_fails_fast_when_child_dies_while_coming_up(
    project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The exact live failure: pid file written, pid briefly alive, then the
    child dies before ever serving. Must fail LOUD, not print 'started'."""
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.3)"])
    try:
        pid_path, _info = dl._resolve_instance_paths(project, None)
        monkeypatch.setattr("veles.daemon.spawn.spawn_daemon", _spawn_stub(child, pid_path))
        args = argparse.Namespace(host="127.0.0.1", port=_free_port())
        started = time.monotonic()
        rc = dl._detach_and_report(args, project, timeout=10.0)
        elapsed = time.monotonic() - started
        assert rc == 1
        assert elapsed < 5.0  # died → fail fast, don't sit out the full timeout
        err = capsys.readouterr().err
        assert "died" in err or "not serving" in err or "did not start" in err
    finally:
        child.wait(timeout=5)


def test_spawn_daemon_routes_child_output_to_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from veles.daemon import spawn as spawn_mod

    seen: dict = {}

    class _FakeProc:
        pid = 12345

    def _fake_popen(cmd, **kwargs):
        seen.update(kwargs)
        return _FakeProc()

    monkeypatch.setattr(spawn_mod.subprocess, "Popen", _fake_popen)
    log_path = tmp_path / "logs" / "daemon-p.log"
    spawn_mod.spawn_daemon(project_root=tmp_path, host="127.0.0.1", port=8765, log_path=log_path)
    # stdout/stderr must land in the log file, not /dev/null.
    assert seen["stdout"] is not spawn_mod.subprocess.DEVNULL
    assert Path(seen["stdout"].name) == log_path
    assert seen["stderr"] == spawn_mod.subprocess.STDOUT
    seen["stdout"].close()


def test_spawn_daemon_without_log_path_keeps_devnull(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from veles.daemon import spawn as spawn_mod

    seen: dict = {}
    monkeypatch.setattr(
        spawn_mod.subprocess, "Popen", lambda cmd, **kw: seen.update(kw) or object()
    )
    spawn_mod.spawn_daemon(project_root=tmp_path, host="127.0.0.1", port=8765)
    assert seen["stdout"] is spawn_mod.subprocess.DEVNULL
    assert seen["stderr"] is spawn_mod.subprocess.DEVNULL


def test_run_app_crash_is_logged_and_reraised(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from veles.cli.commands import daemon as daemon_cmd

    def _boom(app, **kwargs):
        raise OSError("[Errno 48] address already in use")

    monkeypatch.setattr(daemon_cmd.web, "run_app", _boom)
    with (
        caplog.at_level("ERROR", logger="veles.daemon"),
        pytest.raises(OSError, match="address already in use"),
    ):
        daemon_cmd._run_app_logged(object(), host="127.0.0.1", port=8765)
    assert any("crashed" in r.message for r in caplog.records)
    assert any(r.exc_info for r in caplog.records)  # full traceback attached
