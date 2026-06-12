"""M136: channels as a data bus — generic registry-driven channel startup.

`_start_channel_runners` is now generic over `channels/platform_registry` and
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

from veles.channels.platform_registry import register_platform, unregister_platform
from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.core.project_config import list_channel_configs
from veles.daemon.auth import TokenStore
from veles.daemon.server import _channel_session_map, _start_channel_runners
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
    import veles.channels.session_map as sm

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

    _channel_session_map(_S(), "telegram")
    _channel_session_map(_U(), "telegram")
    # Named session is namespaced; unnamed keeps the back-compat bare key.
    assert captured == ["api-telegram", "telegram"]


# ---- generic startup loop ----


class _FakeGateway:
    """Minimal gateway matching the generic factory contract."""

    def __init__(self, *, bot_token, daemon_client, session_map, name="fake"):
        self.bot_token = bot_token
        self.daemon_client = daemon_client
        self.session_map = session_map
        self.name = name
        self.started = False

    async def start(self):
        self.started = True

    async def stop(self):
        pass


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
    register_platform("fake", _FakeGateway, overwrite=True)
    register_platform("fake2", _FakeGateway, overwrite=True)
    yield
    unregister_platform("fake")
    unregister_platform("fake2")


def _write_config(project, body: str) -> None:
    (project.state_dir / "config.toml").write_text(body, encoding="utf-8")


async def test_generic_loop_starts_registered_channel(state, fake_platforms):
    _write_config(state.project, '[channels.fake]\nenabled = true\nbot_token = "tok"\n')
    _start_channel_runners(state)
    assert len(state.channel_runners) == 1
    assert state.channel_runners[0].bot_token == "tok"
    for task in list(state.channel_tasks):
        await asyncio.wait_for(task, timeout=2.0)
    assert state.channel_runners[0].started is True


async def test_two_channels_one_daemon(state, fake_platforms):
    _write_config(
        state.project,
        '[channels.fake]\nenabled = true\nbot_token = "a"\n'
        '[channels.fake2]\nenabled = true\nbot_token = "b"\n',
    )
    _start_channel_runners(state)
    assert len(state.channel_runners) == 2
    tokens = sorted(g.bot_token for g in state.channel_runners)
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
        _start_channel_runners(state)
    assert len(state.channel_runners) == 1
    assert state.channel_runners[0].bot_token == "a"
    assert any("no bot token" in r.message for r in caplog.records)
    for task in list(state.channel_tasks):
        await asyncio.wait_for(task, timeout=2.0)


def test_unregistered_platform_skipped(state, caplog):
    _write_config(state.project, '[channels.nope]\nenabled = true\nbot_token = "x"\n')
    with caplog.at_level(logging.WARNING, logger="veles.daemon.server"):
        _start_channel_runners(state)
    assert state.channel_runners == []
    assert any("not a registered platform" in r.message for r in caplog.records)


async def test_named_session_reads_own_channels(state, fake_platforms):
    state.session_name = "api"
    _write_config(
        state.project,
        '[channels.fake]\nenabled = true\nbot_token = "global"\n'
        '[daemon.api.channels.fake2]\nenabled = true\nbot_token = "scoped"\n',
    )
    _start_channel_runners(state)
    # Only the session-scoped channel starts; the global one is ignored.
    assert len(state.channel_runners) == 1
    assert state.channel_runners[0].bot_token == "scoped"
    for task in list(state.channel_tasks):
        await asyncio.wait_for(task, timeout=2.0)
