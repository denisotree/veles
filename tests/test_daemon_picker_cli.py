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
