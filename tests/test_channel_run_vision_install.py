"""M226 — `veles channel run` installs the vision adapter itself.

`channel` is dispatched before the CLI's own `set_active_project`, so the
standalone gateway has to resolve the project on its own. It used to skip
installation silently when it couldn't — which looks exactly like the bug
this milestone fixes (file saved, no description), with nothing in the
output saying why.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from veles.cli.commands import channel as channel_cmd
from veles.core.context import reset_active_project, set_active_project
from veles.core.project import init_project
from veles.modules.vision import get_vision_adapter, reset_vision_adapter


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch):
    from veles.channels.platform_registry import ensure_builtins_registered

    ensure_builtins_registered()
    reset_vision_adapter()
    token = set_active_project(None)
    monkeypatch.setattr(channel_cmd.asyncio, "run", lambda coro: coro.close() or 0)
    yield
    reset_active_project(token)
    reset_vision_adapter()


def _args() -> argparse.Namespace:
    return argparse.Namespace(
        channel="telegram",
        bot_token="T",
        daemon_url="http://127.0.0.1:8765",
        daemon_token="D",
    )


def test_installs_the_adapter_for_the_cwd_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    init_project(tmp_path, name="chan")
    monkeypatch.chdir(tmp_path)
    assert channel_cmd._cmd_channel_run(_args()) == 0
    assert get_vision_adapter() is not None


def test_warns_instead_of_silently_skipping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.chdir(tmp_path)  # no project here
    assert channel_cmd._cmd_channel_run(_args()) == 0
    assert get_vision_adapter() is None
    assert "won't be described" in capsys.readouterr().err
