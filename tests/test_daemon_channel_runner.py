"""Daemon-side `start_channel_runners` reads `.veles/config.toml` and
spawns in-process channel gateways — here the test platform `fake`, whose
gateway only records that it started.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.core.secrets import set_provider_key
from veles.daemon.auth import TokenStore
from veles.daemon.channels import start_channel_runners
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


def test_daemon_builds_a_module_platform_from_context(state: DaemonState, fake_platform) -> None:
    """`[channels.fake]` + a keychain token → the gateway is built through
    `spec.build(ctx)`: config and secrets arrive in the context, no platform branch."""
    from veles.daemon.channels import _build_channel_gateway

    set_provider_key("fake", "tok", project=state.project.name)
    gw = _build_channel_gateway(
        "fake", {"enabled": True, "room": "r1"}, backend=object(), state=state
    )
    assert gw is not None
    assert gw.ctx.config["room"] == "r1" and gw.ctx.secrets == {"token": "tok"}
    assert gw.ctx.project is state.project and gw.ctx.name == "fake"


def test_no_config_means_no_channel_runners(state: DaemonState) -> None:
    start_channel_runners(state)
    assert state.channel_runners == []
    assert state.channel_tasks == []


def test_disabled_channel_skipped(state: DaemonState, fake_platform) -> None:
    _write_config(state.project, "[channels.fake]\nenabled = false\n")
    start_channel_runners(state)
    assert state.channel_runners == []


def test_enabled_but_no_token_skipped(state: DaemonState, caplog, fake_platform) -> None:
    import logging

    _write_config(state.project, '[channels.fake]\nenabled = true\nrooms = ["@foo"]\n')
    with caplog.at_level(logging.WARNING, logger="veles.daemon.server"):
        start_channel_runners(state)
    assert state.channel_runners == []
    # M110: warning now lands in the logger (and the daemon log file),
    # not on stderr — that's how the picker's log view will surface it.
    assert any("missing token" in rec.message for rec in caplog.records)
    assert any("veles channel add --channel fake" in rec.getMessage() for rec in caplog.records)


async def test_enabled_with_keychain_token_starts_gateway(
    state: DaemonState, fake_platform
) -> None:
    import asyncio

    set_provider_key("fake", "tok-test", project=state.project.name)
    _write_config(state.project, '[channels.fake]\nenabled = true\nrooms = ["@foo", "12345"]\n')

    start_channel_runners(state)
    assert len(state.channel_runners) == 1
    gateway = state.channel_runners[0]
    assert gateway.ctx.secrets == {"token": "tok-test"}
    assert gateway.ctx.config["rooms"] == ["@foo", "12345"]

    for task in list(state.channel_tasks):
        await asyncio.wait_for(task, timeout=2.0)
    assert gateway.started
