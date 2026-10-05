"""M136: channels as a data bus — generic registry-driven channel startup.

`start_channel_runners` is now generic over `platform` contributions and
over several channels per daemon; a named session reads its own
`[daemon.<name>.channels.*]` (independent contexts via per-(session,platform)
SessionMap), and a bad/credless channel is skipped without aborting the others.
The legacy single-telegram path is covered by `test_daemon_channel_runner.py`.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import pytest

from tests.channels.fake_platform import contributing, fake_spec
from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.core.project_config import list_channel_configs
from veles.daemon.auth import TokenStore
from veles.daemon.channels import channel_session_map, start_channel_runners
from veles.daemon.state import DaemonState

# ---- list_channel_configs (pure config parsing) ----


def test_list_channel_configs_global_only_enabled():
    cfg = {
        "channels": {
            "telegram": {"enabled": True, "whitelist": ["1"]},
            "slack": {"enabled": False},
        }
    }
    assert list_channel_configs(cfg) == [("telegram", {"enabled": True, "whitelist": ["1"]})]


def test_list_channel_configs_per_session_isolated_from_global():
    cfg = {
        "channels": {"telegram": {"enabled": True}},
        "daemon": {
            "api": {"channels": {"discord": {"enabled": True, "bot_token": "x"}}},
        },
    }
    # Named session reads ONLY its own channels (no global telegram leak).
    assert list_channel_configs(cfg, daemon_session="api") == [
        ("discord", {"enabled": True, "bot_token": "x"})
    ]
    # The unnamed daemon reads the global block.
    assert list_channel_configs(cfg) == [("telegram", {"enabled": True})]


def test_list_channel_configs_sorted_and_empty():
    assert list_channel_configs({}) == []
    cfg = {"channels": {"zeta": {"enabled": True}, "alpha": {"enabled": True}}}
    assert [p for p, _ in list_channel_configs(cfg)] == ["alpha", "zeta"]


# ---- session-map keying (independent contexts) ----


def test_channel_session_map_keying(monkeypatch, tmp_path):
    import veles.core.chat_sessions as sm

    captured: list[str] = []
    real = sm.channel_session_path

    def spy(channel, **kw):
        captured.append(channel)
        return real(channel, base_dir=tmp_path)

    monkeypatch.setattr(sm, "channel_session_path", spy)

    class _S:
        session_name = "api"

    class _U:
        session_name = None

    channel_session_map(_S(), "telegram")
    channel_session_map(_U(), "telegram")
    # Named session is namespaced; unnamed keeps the back-compat bare key.
    assert captured == ["api-telegram", "telegram"]


# ---- generic startup loop ----


@pytest.fixture()
def state(tmp_path: Path) -> DaemonState:
    project = init_project(tmp_path, name=None, force=False)
    store = SessionStore(project.memory_db_path)
    return DaemonState(
        project=project,
        store=store,
        token_store=TokenStore.load(),
        agent_factory=lambda *a, **k: None,
        started_at=0.0,
    )


@pytest.fixture()
def fake_platforms():
    spec = fake_spec(secret_key="bot_token")
    with contributing({"fake": spec, "fake2": spec}):
        yield


def _token(gateway) -> str:
    return gateway.ctx.secrets["bot_token"]


def _write_config(project, body: str) -> None:
    (project.state_dir / "config.toml").write_text(body, encoding="utf-8")


async def test_generic_loop_starts_registered_channel(state, fake_platforms):
    _write_config(state.project, '[channels.fake]\nenabled = true\nbot_token = "tok"\n')
    start_channel_runners(state)
    assert len(state.channel_runners) == 1
    assert _token(state.channel_runners[0]) == "tok"
    for task in list(state.channel_tasks):
        await asyncio.wait_for(task, timeout=2.0)
    assert state.channel_runners[0].started is True


async def test_two_channels_one_daemon(state, fake_platforms):
    _write_config(
        state.project,
        '[channels.fake]\nenabled = true\nbot_token = "a"\n'
        '[channels.fake2]\nenabled = true\nbot_token = "b"\n',
    )
    start_channel_runners(state)
    assert len(state.channel_runners) == 2
    tokens = sorted(_token(g) for g in state.channel_runners)
    assert tokens == ["a", "b"]
    for task in list(state.channel_tasks):
        await asyncio.wait_for(task, timeout=2.0)


async def test_credless_channel_skipped_others_survive(state, fake_platforms, caplog):
    _write_config(
        state.project,
        '[channels.fake]\nenabled = true\nbot_token = "a"\n'
        "[channels.fake2]\nenabled = true\n",  # no token
    )
    with caplog.at_level(logging.WARNING, logger="veles.daemon.server"):
        start_channel_runners(state)
    assert len(state.channel_runners) == 1
    assert _token(state.channel_runners[0]) == "a"
    assert any("missing bot_token" in r.message for r in caplog.records)
    for task in list(state.channel_tasks):
        await asyncio.wait_for(task, timeout=2.0)


def test_unregistered_platform_skipped(state, caplog):
    _write_config(state.project, '[channels.nope]\nenabled = true\nbot_token = "x"\n')
    with caplog.at_level(logging.WARNING, logger="veles.daemon.server"):
        start_channel_runners(state)
    assert state.channel_runners == []
    assert any("no installed module provides" in r.message for r in caplog.records)


async def test_named_session_reads_own_channels(state, fake_platforms):
    state.session_name = "api"
    _write_config(
        state.project,
        '[channels.fake]\nenabled = true\nbot_token = "global"\n'
        '[daemon.api.channels.fake2]\nenabled = true\nbot_token = "scoped"\n',
    )
    start_channel_runners(state)
    # Only the session-scoped channel starts; the global one is ignored.
    assert len(state.channel_runners) == 1
    assert _token(state.channel_runners[0]) == "scoped"
    for task in list(state.channel_tasks):
        await asyncio.wait_for(task, timeout=2.0)
