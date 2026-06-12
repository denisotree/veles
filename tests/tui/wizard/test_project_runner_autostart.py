"""TUI project wizard autospawns `veles daemon start` after the user
agreed to the DaemonModeStep. Verified by stubbing `spawn_daemon` so
no real subprocess is launched.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import veles.tui.wizard.project_runner as runner_mod
from veles.core.project import init_project


def test_autostart_called_when_daemon_answered(tmp_path: Path, monkeypatch) -> None:
    project = init_project(tmp_path, name=None, force=False)
    calls: list[dict[str, Any]] = []

    class _FakeProc:
        pid = 4242

    def fake_spawn(*, project_root, host, port):
        calls.append({"project_root": str(project_root), "host": host, "port": port})
        return _FakeProc()

    monkeypatch.setattr(runner_mod, "spawn_daemon", fake_spawn, raising=False)
    # The internal _autostart_daemon imports spawn_daemon lazily, so we
    # patch the symbol both on the runner module and on its source.
    import veles.daemon.spawn as spawn_mod

    monkeypatch.setattr(spawn_mod, "spawn_daemon", fake_spawn)

    runner_mod._autostart_daemon(project, {"host": "127.0.0.1", "port": 8765})

    assert calls == [{"project_root": str(project.root), "host": "127.0.0.1", "port": 8765}]


def test_autostart_handles_spawn_failure(tmp_path: Path, monkeypatch, capsys) -> None:
    project = init_project(tmp_path, name=None, force=False)

    import veles.daemon.spawn as spawn_mod

    monkeypatch.setattr(spawn_mod, "spawn_daemon", lambda **_: None)
    runner_mod._autostart_daemon(project, {"host": "127.0.0.1", "port": 8765})
    captured = capsys.readouterr()
    assert "failed to spawn" in captured.err
