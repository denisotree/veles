"""M97: multi-daemon registry."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from veles.daemon.registry import (
    DaemonEntry,
    DaemonRegistry,
    is_alive,
    registry_path,
    status_for,
    uptime_seconds,
)


@pytest.fixture(autouse=True)
def _isolate_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "veles"))
    return tmp_path


def _entry(slug: str = "demo", **kw) -> DaemonEntry:
    return DaemonEntry(
        slug=slug,
        project_path=kw.get("project_path", "/some/where"),
        project_name=kw.get("project_name", slug),
        pid=kw.get("pid", os.getpid()),
        host=kw.get("host", "127.0.0.1"),
        port=kw.get("port", 8765),
        started_at=kw.get("started_at", 1700000000.0),
    )


def _restart_harness(monkeypatch, tmp_path: Path):
    import veles.cli.commands.daemon as daemon_cmd
    import veles.daemon.spawn as spawn_mod
    from veles.core.project import init_project

    project = init_project(tmp_path / "proj", name="demo")
    reg = DaemonRegistry()
    reg.upsert(_entry("demo", project_path=str(project.root), project_name="demo", port=9001))
    reg.save()
    stopped: list[int] = []
    spawned: dict = {}

    class _Proc:
        pid = 4242

    monkeypatch.setattr(
        daemon_cmd, "_graceful_stop", lambda pid, timeout: stopped.append(pid) or True
    )
    monkeypatch.setattr(spawn_mod, "spawn_daemon", lambda **kw: spawned.update(kw) or _Proc())
    return daemon_cmd, project, stopped, spawned


def test_registry_restart_stops_gracefully_and_respawns_with_a_log(
    monkeypatch, tmp_path, fake_channel
) -> None:
    """`veles daemon <id> restart` goes through the same stop/spawn as the named path:
    SIGTERM→SIGKILL escalation and a detached child that logs to the daemon log."""
    import argparse

    daemon_cmd, project, stopped, spawned = _restart_harness(monkeypatch, tmp_path)
    rc = daemon_cmd._cmd_daemon_restart(argparse.Namespace(target="demo", name=None))

    assert rc == 0
    assert stopped == [os.getpid()]
    assert spawned["project_root"] == str(project.root)
    assert spawned["port"] == 9001
    assert str(spawned["log_path"]).endswith(".log")


def test_restart_without_a_ready_channel_leaves_the_running_daemon_alone(
    monkeypatch, tmp_path, capsys
) -> None:
    """The new daemon would refuse to start; stopping the old one first would
    take a working bot down and still report success."""
    import argparse

    daemon_cmd, _project, stopped, spawned = _restart_harness(monkeypatch, tmp_path)
    rc = daemon_cmd._cmd_daemon_restart(argparse.Namespace(target="demo", name=None))

    assert rc == 1 and stopped == [] and spawned == {}
    assert "channel" in capsys.readouterr().err


def test_restart_of_a_daemon_whose_project_is_gone_says_so(monkeypatch, tmp_path, capsys) -> None:
    import argparse
    import shutil

    daemon_cmd, project, stopped, spawned = _restart_harness(monkeypatch, tmp_path)
    shutil.rmtree(project.root)
    rc = daemon_cmd._cmd_daemon_restart(argparse.Namespace(target="demo", name=None))

    assert rc == 1 and stopped == [] and spawned == {}
    assert str(project.root) in capsys.readouterr().err


def test_the_picker_reports_a_gone_project_instead_of_crashing(tmp_path) -> None:
    from veles.tui.screens._daemon_picker_data import DaemonNode, channel_blocker

    node = DaemonNode(
        key="k",
        kind="registry",
        name="default",
        host=None,
        port=None,
        pid=1,
        status="running",
        model=None,
        project_path=str(tmp_path / "gone"),
    )
    assert "gone" in (channel_blocker(node) or "")


def test_named_restart_without_a_ready_channel_leaves_it_alone(
    monkeypatch, tmp_path, capsys
) -> None:
    import argparse

    import veles.cli.commands.daemon_lifecycle as lifecycle

    daemon_cmd, project, stopped, spawned = _restart_harness(monkeypatch, tmp_path)
    monkeypatch.setattr(lifecycle, "_graceful_stop", lambda pid, timeout: stopped.append(pid))
    monkeypatch.setattr(lifecycle, "read_pid", lambda path: os.getpid())
    monkeypatch.chdir(project.root)
    rc = daemon_cmd._cmd_daemon_restart(argparse.Namespace(target=None, name="api"))

    assert rc == 1 and stopped == [] and spawned == {}
    assert "channel" in capsys.readouterr().err


def test_load_returns_empty_when_missing() -> None:
    reg = DaemonRegistry.load()
    assert reg.entries == {}
    assert reg.list() == []


def test_upsert_then_save_then_load_round_trip() -> None:
    reg = DaemonRegistry()
    reg.upsert(_entry("alpha"))
    reg.save()
    reloaded = DaemonRegistry.load()
    assert "alpha" in reloaded.entries
    assert reloaded.entries["alpha"].port == 8765


def test_get_by_slug_or_project_name() -> None:
    reg = DaemonRegistry()
    reg.upsert(_entry("alpha", project_name="Alpha Project"))
    assert reg.get("alpha") is not None
    assert reg.get("Alpha Project") is not None
    assert reg.get("ghost") is None


def test_remove_deletes_entry() -> None:
    reg = DaemonRegistry()
    reg.upsert(_entry("alpha"))
    assert reg.remove("alpha") is True
    assert reg.remove("alpha") is False
    assert reg.list() == []


def test_list_is_sorted_by_slug() -> None:
    reg = DaemonRegistry()
    reg.upsert(_entry("zeta"))
    reg.upsert(_entry("alpha"))
    reg.upsert(_entry("mu"))
    assert [e.slug for e in reg.list()] == ["alpha", "mu", "zeta"]


def test_is_alive_for_self_pid_returns_true() -> None:
    assert is_alive(os.getpid()) is True


def test_is_alive_for_zero_pid_returns_false() -> None:
    assert is_alive(0) is False


def test_status_for_running_self() -> None:
    entry = _entry(pid=os.getpid())
    assert status_for(entry) == "running"


def test_status_for_dead_pid() -> None:
    # PID 1 (init) is alive on macOS; a very large pid is reliably dead.
    # A kept-but-dead entry reads "stopped" (entries persist until delete).
    entry = _entry(pid=999_999)
    assert status_for(entry) == "stopped"


def test_uptime_seconds_basic() -> None:
    entry = _entry(started_at=100.0)
    assert uptime_seconds(entry, now=205.0) == pytest.approx(105.0)


def test_uptime_seconds_zero_when_not_started() -> None:
    entry = _entry(started_at=0.0)
    assert uptime_seconds(entry, now=1234.0) == 0.0


def test_registry_path_under_veles_user_home(_isolate_home: Path) -> None:
    # VELES_USER_HOME replaces `~`, so state lands under `<override>/.veles/`
    # — same semantics as core.user_paths.user_home().
    assert registry_path() == _isolate_home / "veles" / ".veles" / "daemons.json"


def test_load_corrupt_file_returns_empty(_isolate_home: Path) -> None:
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ this is not json", encoding="utf-8")
    reg = DaemonRegistry.load()
    assert reg.entries == {}
