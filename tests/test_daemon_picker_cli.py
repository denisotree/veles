"""M197: bare `veles daemon` picker — non-TTY guard + wiring.

The prompt_toolkit Application itself needs a real terminal/event loop and
isn't unit-testable here; these tests cover the testable seams: the non-TTY
fallback to the daemon list, and that a live TTY reaches `run_daemon_picker`.
"""

from __future__ import annotations

import sys

import pytest

from veles.cli.commands import daemon as daemon_cmd


def _ns(**fields):
    return type("A", (), fields)()


def test_picker_falls_back_to_list_without_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Headless / piped `veles daemon` must print the daemon list, never launch
    the picker."""
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

    def _boom(*a, **k):
        raise AssertionError("picker must not launch without a TTY")

    monkeypatch.setattr("veles.cli.commands.daemon_picker_cli.run_daemon_picker", _boom)

    called: dict[str, bool] = {}

    def _fake_list(args) -> int:
        called["list"] = True
        return 0

    monkeypatch.setattr(daemon_cmd, "_cmd_daemon_list", _fake_list)

    rc = daemon_cmd._cmd_daemon_picker(_ns())
    assert rc == 0
    assert called.get("list") is True


def test_picker_falls_back_when_stdout_not_a_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both ends must be a TTY; a piped stdout alone also degrades to the list."""
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    monkeypatch.setattr(
        "veles.cli.commands.daemon_picker_cli.run_daemon_picker",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("picker launched")),
    )
    marker: dict[str, bool] = {}
    monkeypatch.setattr(daemon_cmd, "_cmd_daemon_list", lambda args: marker.setdefault("l", True))
    daemon_cmd._cmd_daemon_picker(_ns())
    assert marker.get("l") is True


def test_picker_launches_with_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """With a real TTY on both ends, `_cmd_daemon_picker` resolves the project
    and hands off to `run_daemon_picker` (the Application itself is not driven
    here)."""
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

    sentinel = object()
    monkeypatch.setattr("veles.cli._resolve_active_project", lambda args: sentinel)

    captured: dict[str, object] = {}

    def _fake_picker(project, *a, **k) -> None:
        captured["project"] = project

    monkeypatch.setattr("veles.cli.commands.daemon_picker_cli.run_daemon_picker", _fake_picker)

    rc = daemon_cmd._cmd_daemon_picker(_ns())
    assert rc == 0
    assert captured.get("project") is sentinel


# ---------------- lifecycle dispatchers (no TTY / Application) ----------------

from veles.cli.commands import daemon_picker_cli as dpc  # noqa: E402
from veles.daemon.picker_data import DaemonNode  # noqa: E402


def _node(kind: str, *, pid: int | None = 0, name: str = "d") -> DaemonNode:
    return DaemonNode(
        key=f"{kind}:{name}",
        kind=kind,
        name=name,
        host="127.0.0.1",
        port=8765,
        pid=pid,
        status="stopped",
        model=None,
    )


def test_do_start_spawns_registry_daemon(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dpc, "is_alive", lambda pid: False)
    monkeypatch.setattr(dpc, "spawn_daemon_node", lambda node: True)
    assert dpc._do_start(None, _node("registry")) == "d: start spawned"


def test_do_start_reports_already_running(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dpc, "is_alive", lambda pid: True)
    assert dpc._do_start(None, _node("registry", pid=42)) == "d: already running"


def test_do_start_rejects_tui_session() -> None:
    assert "not applicable" in dpc._do_start(None, _node("tui"))


def test_do_start_named_delegates_to_runtime_action(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dpc, "is_alive", lambda pid: False)
    seen: dict[str, object] = {}

    def _act(project, record, action):
        seen["action"] = action
        return "d: start spawned"

    monkeypatch.setattr(dpc, "runtime_session_action", _act)
    assert dpc._do_start(None, _node("named", pid=None)) == "d: start spawned"
    assert seen["action"] == "start"


def test_do_stop_sigterms_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dpc, "is_alive", lambda pid: True)
    killed: list[tuple[int, int]] = []
    monkeypatch.setattr("os.kill", lambda pid, sig: killed.append((pid, sig)))
    msg = dpc._do_stop(None, _node("registry", pid=99))
    assert "SIGTERM sent" in msg
    assert killed and killed[0][0] == 99


def test_do_stop_reports_not_running(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dpc, "is_alive", lambda pid: False)
    assert dpc._do_stop(None, _node("registry", pid=0)) == "d: not running"


def test_do_restart_kills_then_spawns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dpc, "is_alive", lambda pid: False)  # already dead → no wait
    monkeypatch.setattr(dpc, "spawn_daemon_node", lambda node: True)
    assert dpc._do_restart(None, _node("registry")) == "d: restart spawned"


def test_do_delete_registry_removes_from_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dpc, "is_alive", lambda pid: False)
    monkeypatch.setattr("veles.cli.repl.simple._choice_picker", lambda t, q, o: "Yes")

    removed: list[str] = []

    class _FakeReg:
        @classmethod
        def load(cls):
            return cls()

        def remove(self, slug):
            removed.append(slug)

        def save(self):
            pass

    monkeypatch.setattr("veles.daemon.registry.DaemonRegistry", _FakeReg)

    from veles.daemon.registry import DaemonEntry

    node = _node("registry")
    node.entry = DaemonEntry(
        slug="alpha",
        project_path="/p",
        project_name="alpha",
        pid=0,
        host="h",
        port=1,
        started_at=0.0,
    )
    assert dpc._do_delete(None, node, theme=None) == "d: deleted"
    assert removed == ["alpha"]


def test_do_delete_cancelled_leaves_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("veles.cli.repl.simple._choice_picker", lambda t, q, o: "No")
    assert dpc._do_delete(None, _node("registry"), theme=None) == "d: delete cancelled"


def test_do_delete_named_soft_deletes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dpc, "is_alive", lambda pid: False)
    monkeypatch.setattr("veles.cli.repl.simple._choice_picker", lambda t, q, o: "Yes")
    soft: list[object] = []
    monkeypatch.setattr(dpc, "soft_delete_runtime", lambda project, record: soft.append(record))
    node = _node("named", pid=None)
    node.record = object()
    assert "deleted" in dpc._do_delete(None, node, theme=None)
    assert soft == [node.record]


def test_do_delete_rejects_tui() -> None:
    assert "can't be deleted" in dpc._do_delete(None, _node("tui"), theme=None)


def test_log_hint_named_uses_project_slug() -> None:
    node = _node("named", name="api")
    node.project_name = "myproj"
    hint = dpc._log_hint(node)
    assert "daemon-myproj-api.log" in hint
