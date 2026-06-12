"""Daemon-side `_start_channel_runners` reads `.veles/config.toml` and
spawns in-process channel gateways. We mock the TelegramGateway's
network surface (`_telegram_send` + getUpdates returning []) so the
test loop exits cleanly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.core.secrets import set_provider_key
from veles.daemon.auth import TokenStore
from veles.daemon.server import _start_channel_runners
from veles.daemon.state import DaemonState


@pytest.fixture()
def state(tmp_path: Path) -> DaemonState:
    project = init_project(tmp_path, name=None, force=False)
    store = SessionStore(project.memory_db_path)
    tokens = TokenStore.load()

    def factory(session_id):
        raise AssertionError("agent factory must not be called when no message arrives")

    return DaemonState(
        project=project,
        store=store,
        token_store=tokens,
        agent_factory=factory,
        started_at=0.0,
    )


def _write_config(project, body: str) -> None:
    cfg = project.state_dir / "config.toml"
    cfg.write_text(body, encoding="utf-8")


def test_no_config_means_no_channel_runners(state: DaemonState) -> None:
    _start_channel_runners(state)
    assert state.channel_runners == []
    assert state.channel_tasks == []


def test_disabled_telegram_skipped(state: DaemonState) -> None:
    _write_config(
        state.project,
        "[channels.telegram]\nenabled = false\nwhitelist = []\n",
    )
    _start_channel_runners(state)
    assert state.channel_runners == []


def test_enabled_but_no_token_skipped(state: DaemonState, caplog) -> None:
    import logging

    _write_config(
        state.project,
        '[channels.telegram]\nenabled = true\nwhitelist = ["@foo"]\n',
    )
    with caplog.at_level(logging.WARNING, logger="veles.daemon.server"):
        _start_channel_runners(state)
    assert state.channel_runners == []
    # M110: warning now lands in the logger (and the daemon log file),
    # not on stderr — that's how the picker's log view will surface it.
    assert any("no bot token" in rec.message for rec in caplog.records)


async def test_enabled_with_keychain_token_starts_gateway(state: DaemonState, monkeypatch) -> None:
    set_provider_key("telegram", "tok-test", project=state.project.name)
    _write_config(
        state.project,
        '[channels.telegram]\nenabled = true\nwhitelist = ["@foo", "12345"]\n',
    )
    # Stub TelegramGateway.start so we don't enter the real poll loop.
    started: list[bool] = []
    stopped: list[bool] = []

    async def fake_start(self):
        started.append(True)

    async def fake_stop(self):
        stopped.append(True)

    from veles.channels import telegram as tg_mod

    monkeypatch.setattr(tg_mod.TelegramGateway, "start", fake_start)
    monkeypatch.setattr(tg_mod.TelegramGateway, "stop", fake_stop)

    _start_channel_runners(state)
    assert len(state.channel_runners) == 1
    gateway = state.channel_runners[0]
    assert gateway.bot_token == "tok-test"
    assert gateway.whitelist == ("@foo", "12345")

    # Let the asyncio task run.
    import asyncio

    for task in list(state.channel_tasks):
        await asyncio.wait_for(task, timeout=2.0)
    assert started == [True]

    # Clean up keychain entry to avoid polluting other tests.
    from veles.core.secrets import delete_provider_key

    delete_provider_key("telegram", project=state.project.name)


async def test_legacy_chat_id_promoted_to_whitelist(state: DaemonState, monkeypatch) -> None:
    set_provider_key("telegram", "tok-test", project=state.project.name)
    _write_config(
        state.project,
        '[channels.telegram]\nenabled = true\nchat_id = "555"\n',
    )

    async def fake_start(self):
        pass

    from veles.channels import telegram as tg_mod

    monkeypatch.setattr(tg_mod.TelegramGateway, "start", fake_start)

    _start_channel_runners(state)
    assert state.channel_runners[0].whitelist == ("555",)

    import asyncio

    for task in list(state.channel_tasks):
        await asyncio.wait_for(task, timeout=2.0)

    from veles.core.secrets import delete_provider_key

    delete_provider_key("telegram", project=state.project.name)
