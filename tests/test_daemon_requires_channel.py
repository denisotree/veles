"""A daemon is the host of channels: with no working one it does not start."""

from __future__ import annotations

import contextvars

import pytest

from tests.test_daemon_detach import _start_args
from veles.cli.commands import daemon as daemon_cmd
from veles.core.channel_setup import channel_readiness, no_channel_message
from veles.core.project import init_project
from veles.core.project_config import load_project_config, save_project_config


@pytest.fixture()
def project(tmp_path, monkeypatch):
    project = init_project(tmp_path / "p", name="p")
    monkeypatch.chdir(project.root)
    monkeypatch.setattr("veles.cli._console.ensure_api_key", lambda provider, project=None: True)
    monkeypatch.setenv("VELES_NO_WIZARD", "1")
    return project


def _declare(project, channels: dict) -> None:
    cfg = load_project_config(project)
    cfg["channels"] = channels
    save_project_config(project, cfg)


def test_readiness_reports_each_declared_channel(project, fake_platform) -> None:
    _declare(project, {"fake": {"enabled": True}, "ghost": {"enabled": True}})
    states = {s.name: s.state for s in channel_readiness(project, None)}
    assert states == {"fake": "no_creds", "ghost": "no_module"}
    _declare(project, {"fake": {"enabled": True, "token": "t"}})
    assert [s.state for s in channel_readiness(project, None)] == ["ok"]


def test_the_message_names_each_fix(project, fake_platform) -> None:
    _declare(project, {"fake": {"enabled": True}, "ghost": {"enabled": True}})
    message = no_channel_message(channel_readiness(project, None), None)
    assert "veles channel add --channel fake" in message and "install ghost" in message
    assert "veles channel add" in no_channel_message([], None)


def test_foreground_daemon_without_a_channel_exits_before_serving(project, monkeypatch, capsys):
    served: list[bool] = []
    monkeypatch.setattr(daemon_cmd, "_run_app_logged", lambda *a, **k: served.append(True))
    rc = contextvars.copy_context().run(daemon_cmd._cmd_daemon_start, _start_args(foreground=True))
    assert rc == 1 and served == []
    assert "veles channel add" in capsys.readouterr().err


def test_detaching_start_without_a_channel_refuses_before_spawning(project, monkeypatch, capsys):
    spawned: list[bool] = []
    monkeypatch.setattr(daemon_cmd, "_detach_and_report", lambda *a, **k: spawned.append(True) or 0)
    rc = contextvars.copy_context().run(daemon_cmd._cmd_daemon_start, _start_args())
    assert rc == 1 and spawned == []


def test_a_ready_channel_lets_the_daemon_start(project, fake_platform, monkeypatch) -> None:
    _declare(project, {"fake": {"enabled": True, "token": "t"}})
    spawned: list[bool] = []
    monkeypatch.setattr(daemon_cmd, "_detach_and_report", lambda *a, **k: spawned.append(True) or 0)
    rc = contextvars.copy_context().run(daemon_cmd._cmd_daemon_start, _start_args())
    assert rc == 0 and spawned == [True]
