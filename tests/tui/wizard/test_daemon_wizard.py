"""`veles daemon start` Textual wizard (live 2026-07-09).

An interactive `daemon start` with no channel configured must walk the user
through the start steps in the same modal style as the project wizard —
bind (host/port, persisted to the project config) then the registry-driven
channel flow — not a bare stdin `[y/N]` prompt.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from tests.conftest import FakeKeyring as _FakeKeyring
from veles.core import secrets
from veles.core.project import init_project
from veles.tui.wizard.app import WizardApp
from veles.tui.wizard.daemon_steps import daemon_start_steps


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _FakeKeyring:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "veles"))
    kr = _FakeKeyring()
    monkeypatch.setattr(secrets, "_keyring", lambda: (kr, kr.errors))
    return kr


@pytest.fixture
def project(tmp_path: Path):
    return init_project(tmp_path / "proj", name="proj")


async def _drive(steps, keys: list[str], poll: int = 120) -> dict:
    app = WizardApp(steps=steps)
    async with app.run_test() as pilot:
        await pilot.pause()
        for k in keys:
            await pilot.press(k)
            await pilot.pause()
        for _ in range(poll):
            if app.result is not None or app.is_running is False:
                break
            await pilot.pause()
        return dict(app.result or {})


def _cfg(project) -> dict:
    with open(project.state_dir / "config.toml", "rb") as fh:
        return tomllib.load(fh)


async def test_bind_defaults_accepted_channel_declined(project) -> None:
    steps = daemon_start_steps(project, session=None, host="127.0.0.1", port=8765)
    answers = await _drive(steps, ["enter", "enter", "n"])
    assert answers["daemon_bind"] == {"host": "127.0.0.1", "port": 8765}
    assert answers["channel"] is None
    cfg = _cfg(project)
    assert cfg["daemon"]["enabled"] is True
    assert cfg["daemon"]["host"] == "127.0.0.1"
    assert cfg["daemon"]["port"] == 8765


async def test_channel_accepted_persists_via_registry(project) -> None:
    steps = daemon_start_steps(project, session=None, host="127.0.0.1", port=8765)
    keys = [
        "enter",  # host default
        "enter",  # port default
        "y",  # connect a channel? yes
        "enter",  # channel type picker → telegram (default)
        *list("token"),
        "enter",  # bot_token cred
        *list("@foo"),
        "enter",  # whitelist cred
    ]
    answers = await _drive(steps, keys)
    assert answers["channel"]["channel"] == "telegram"
    assert answers["channel"]["status"] == "saved"
    assert secrets.get_provider_key("telegram", project=project.name) == "token"
    cfg = _cfg(project)
    assert cfg["channels"]["telegram"]["enabled"] is True
    assert cfg["channels"]["telegram"]["whitelist"] == ["@foo"]


async def test_named_session_persists_to_its_own_block(project) -> None:
    steps = daemon_start_steps(project, session="work", host="0.0.0.0", port=9100)
    answers = await _drive(steps, ["enter", "enter", "n"])
    assert answers["daemon_bind"] == {"host": "0.0.0.0", "port": 9100}
    cfg = _cfg(project)
    assert cfg["daemon"]["work"]["enabled"] is True
    assert cfg["daemon"]["work"]["host"] == "0.0.0.0"
    assert cfg["daemon"]["work"]["port"] == 9100
