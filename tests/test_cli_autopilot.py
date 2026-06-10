"""M63 — `veles autopilot` CLI verb tests."""

from __future__ import annotations

import json
import time

from veles.cli.commands import autopilot as autopilot_cmd
from veles.core.autopilot import autopilot_path


# User-home isolation is provided by the autouse `_hermetic_user_home`
# fixture in tests/conftest.py.


def _ns(**fields):
    return type("A", (), fields)()


def test_enable_writes_state_file(capsys) -> None:
    args = _ns(autopilot_command="enable", until="+2h")
    rc = autopilot_cmd.cmd_autopilot(args)
    assert rc == 0
    err = capsys.readouterr().err
    assert "autopilot enabled" in err
    path = autopilot_path()
    assert path.is_file()
    body = json.loads(path.read_text(encoding="utf-8"))
    assert body["enabled_until"] > time.time() + 3500


def test_enable_rejects_past_timestamp(capsys) -> None:
    args = _ns(autopilot_command="enable", until="2020-01-01T00:00:00Z")
    rc = autopilot_cmd.cmd_autopilot(args)
    assert rc == 2
    err = capsys.readouterr().err
    assert "future" in err


def test_enable_rejects_garbage_duration(capsys) -> None:
    args = _ns(autopilot_command="enable", until="banana")
    rc = autopilot_cmd.cmd_autopilot(args)
    assert rc == 2
    assert "not understood" in capsys.readouterr().err


def test_disable_when_not_active(capsys) -> None:
    args = _ns(autopilot_command="disable")
    rc = autopilot_cmd.cmd_autopilot(args)
    assert rc == 0
    assert "not active" in capsys.readouterr().err


def test_disable_after_enable_clears_file(capsys) -> None:
    autopilot_cmd.cmd_autopilot(_ns(autopilot_command="enable", until="+1h"))
    capsys.readouterr()
    rc = autopilot_cmd.cmd_autopilot(_ns(autopilot_command="disable"))
    assert rc == 0
    assert "disabled" in capsys.readouterr().err
    assert not autopilot_path().is_file()


def test_status_inactive_no_history(capsys) -> None:
    rc = autopilot_cmd.cmd_autopilot(_ns(autopilot_command="status"))
    assert rc == 1
    assert "inactive" in capsys.readouterr().out


def test_status_active(capsys) -> None:
    autopilot_cmd.cmd_autopilot(_ns(autopilot_command="enable", until="+1h"))
    capsys.readouterr()
    rc = autopilot_cmd.cmd_autopilot(_ns(autopilot_command="status"))
    assert rc == 0
    out = capsys.readouterr().out
    assert "active" in out
    assert "left" in out


def test_status_after_expiry(capsys) -> None:
    # Manually write expired state.
    autopilot_path().parent.mkdir(parents=True, exist_ok=True)
    autopilot_path().write_text(
        json.dumps({"enabled_until": time.time() - 60}), encoding="utf-8"
    )
    rc = autopilot_cmd.cmd_autopilot(_ns(autopilot_command="status"))
    assert rc == 1
    out = capsys.readouterr().out
    assert "inactive" in out
    assert "last window ended" in out


def test_unknown_subcommand(capsys) -> None:
    rc = autopilot_cmd.cmd_autopilot(_ns(autopilot_command="nope"))
    assert rc == 2
    assert "unknown autopilot" in capsys.readouterr().err
