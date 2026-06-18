"""M116.1: slash-command dispatcher for the Telegram channel.

Unit-tests for `channels/_telegram_commands.py` — parse + dispatch +
menu payload. Handler functions are async; we use pytest-asyncio.

Integration tests (handler reached from `_handle_update`) live in
`test_channels_telegram.py` to stay alongside the rest of the
gateway suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.channels._telegram_commands import (
    dispatch,
    is_known_command,
    menu_descriptors,
    parse_command,
)
from veles.channels.session_map import SessionMap
from veles.channels.telegram import TelegramGateway

# ---- parse_command ----


def test_parse_command_basic() -> None:
    assert parse_command("/help") == ("help", "")
    assert parse_command("/status") == ("status", "")


def test_parse_command_with_args() -> None:
    assert parse_command("/goal ship it") == ("goal", "ship it")
    assert parse_command("/wiki add https://x.io/a") == (
        "wiki",
        "add https://x.io/a",
    )


def test_parse_command_lowercases() -> None:
    assert parse_command("/HELP") == ("help", "")


def test_parse_command_strips_bot_suffix() -> None:
    """Telegram groups address bots as `/cmd@MyBot args`."""
    assert parse_command("/help@VelesBot") == ("help", "")
    assert parse_command("/goal@VelesBot ship it") == ("goal", "ship it")


def test_parse_command_non_command_returns_none() -> None:
    assert parse_command("hello world") is None
    assert parse_command("") is None
    assert parse_command("/") is None  # leading slash but no command
    assert parse_command("  no slash  ") is None


def test_parse_command_trims_whitespace() -> None:
    assert parse_command("  /status  arg  ") == ("status", "arg")


# ---- is_known_command ----


def test_known_commands_include_gateway_owned() -> None:
    """`start` / `reset` are owned by the gateway flow, but they still
    count as known so the gateway never sends them through the message
    buffer."""
    assert is_known_command("start")
    assert is_known_command("reset")


def test_known_commands_include_dispatcher_handled() -> None:
    for cmd in ("help", "status", "session", "tokens", "context"):
        assert is_known_command(cmd), cmd


def test_unknown_command() -> None:
    assert not is_known_command("foobar")


# ---- menu_descriptors ----


def test_menu_descriptors_shape() -> None:
    items = menu_descriptors()
    assert isinstance(items, list)
    assert len(items) >= 5
    for entry in items:
        assert set(entry.keys()) == {"command", "description"}
        assert entry["command"] and entry["description"]


def test_menu_descriptors_no_leading_slash() -> None:
    """Telegram's setMyCommands expects bare names — no leading slash."""
    for entry in menu_descriptors():
        assert not entry["command"].startswith("/")


# ---- dispatch ----


@pytest.fixture()
def session_map(tmp_path: Path) -> SessionMap:
    return SessionMap.load(tmp_path / "telegram-sessions.json")


def _make_gateway(
    session_map: SessionMap,
    *,
    project_root: Path | None = None,
    whitelist: tuple[str, ...] = (),
    attachment_dir: Path | None = None,
) -> TelegramGateway:
    class _NullClient:
        async def submit_run(self, prompt: str, *, session_id=None, origin=None):
            return {"run_id": "x", "session_id": session_id, "state": "running"}

        async def stream_events(self, run_id):
            if False:
                yield  # pragma: no cover

    return TelegramGateway(
        bot_token="X",
        daemon_client=_NullClient(),  # type: ignore[arg-type]
        session_map=session_map,
        whitelist=whitelist,
        project_root=project_root,
        attachment_dir=attachment_dir,
    )


async def test_dispatch_help_returns_command_list(session_map: SessionMap) -> None:
    gateway = _make_gateway(session_map)
    reply = await dispatch(gateway, "42", "help", "")
    assert reply is not None
    assert "/help" in reply
    assert "/status" in reply
    assert "/session" in reply


async def test_dispatch_session_without_session(session_map: SessionMap) -> None:
    gateway = _make_gateway(session_map)
    reply = await dispatch(gateway, "42", "session", "")
    assert reply is not None
    assert "none yet" in reply or "start one" in reply


async def test_dispatch_session_with_active_session(session_map: SessionMap) -> None:
    session_map.set("42", "ses-abc-1234")
    gateway = _make_gateway(session_map)
    reply = await dispatch(gateway, "42", "session", "")
    assert reply is not None
    assert "ses-abc-1234" in reply


async def test_dispatch_status_includes_session_and_project(
    session_map: SessionMap, tmp_path: Path
) -> None:
    session_map.set("42", "ses-abc")
    gateway = _make_gateway(
        session_map,
        project_root=tmp_path / "myproj",
        whitelist=("user1", "user2"),
    )
    reply = await dispatch(gateway, "42", "status", "")
    assert reply is not None
    assert "ses-abc" in reply
    assert "myproj" in reply
    assert "2 entries" in reply


async def test_dispatch_status_open_whitelist(session_map: SessionMap) -> None:
    gateway = _make_gateway(session_map, whitelist=())
    reply = await dispatch(gateway, "42", "status", "")
    assert reply is not None
    assert "open" in reply.lower() or "no whitelist" in reply.lower()


async def test_dispatch_tokens_is_placeholder(session_map: SessionMap) -> None:
    gateway = _make_gateway(session_map)
    reply = await dispatch(gateway, "42", "tokens", "")
    assert reply is not None
    # Must clearly communicate WIP / deferred status.
    assert (
        "not exposed" in reply.lower()
        or "wip" in reply.lower()
        or "deferred" in reply.lower()
        or "/tokens" in reply
    )


async def test_dispatch_context_is_placeholder(session_map: SessionMap) -> None:
    gateway = _make_gateway(session_map)
    reply = await dispatch(gateway, "42", "context", "")
    assert reply is not None
    assert "/context" in reply or "not exposed" in reply.lower()


async def test_dispatch_goal_without_task_returns_usage(
    session_map: SessionMap,
) -> None:
    gateway = _make_gateway(session_map)
    reply = await dispatch(gateway, "42", "goal", "")
    assert reply is not None
    # Empty task = usage hint, no submit_run call expected
    assert "long-running" in reply or "&lt;task&gt;" in reply


async def test_dispatch_goal_with_task_submits_run(session_map: SessionMap) -> None:
    submitted: list[tuple[str, str | None]] = []

    class _Client:
        async def submit_run(self, prompt: str, *, session_id=None, origin=None):
            submitted.append((prompt, session_id))
            return {"run_id": "g1", "session_id": session_id, "state": "running"}

        async def stream_events(self, run_id):
            if False:
                yield

    from veles.channels.telegram import TelegramGateway

    gateway = TelegramGateway(
        bot_token="X",
        daemon_client=_Client(),  # type: ignore[arg-type]
        session_map=session_map,
    )
    session_map.set("42", "sess-abc")

    reply = await dispatch(gateway, "42", "goal", "deploy to staging")
    assert reply is not None
    assert "deploy" in reply
    assert submitted, "goal-mode should submit one run"
    prompt, session = submitted[0]
    assert "[GOAL MODE]" in prompt
    assert "deploy to staging" in prompt
    assert session == "sess-abc"


async def test_dispatch_dream_submits_consolidation_run(
    session_map: SessionMap,
) -> None:
    submitted: list[str] = []

    class _Client:
        async def submit_run(self, prompt: str, *, session_id=None, origin=None):
            submitted.append(prompt)
            return {"run_id": "d1", "session_id": session_id, "state": "running"}

        async def stream_events(self, run_id):
            if False:
                yield

    from veles.channels.telegram import TelegramGateway

    gateway = TelegramGateway(
        bot_token="X",
        daemon_client=_Client(),  # type: ignore[arg-type]
        session_map=session_map,
    )
    reply = await dispatch(gateway, "42", "dream", "")
    assert reply is not None
    assert "consolidation" in reply.lower()
    assert submitted
    assert "[DREAM MODE]" in submitted[0]


async def test_goal_dream_appear_in_menu_descriptors() -> None:
    from veles.channels._telegram_commands import menu_descriptors

    cmds = {d["command"] for d in menu_descriptors()}
    assert "goal" in cmds
    assert "dream" in cmds


async def test_help_lists_goal_and_dream(session_map: SessionMap) -> None:
    gateway = _make_gateway(session_map)
    reply = await dispatch(gateway, "42", "help", "")
    assert reply is not None
    assert "/goal" in reply
    assert "/dream" in reply


async def test_all_command_names_includes_owned_and_handled() -> None:
    from veles.channels._telegram_commands import all_command_names

    names = all_command_names()
    assert "start" in names
    assert "reset" in names
    assert "goal" in names
    assert "dream" in names
    # Sorted
    assert names == sorted(names)


async def test_dispatch_unknown_command_returns_none(session_map: SessionMap) -> None:
    """`start`/`reset` are gateway-owned — dispatch returns None so the
    gateway's existing flow handles them. Same for truly unknown commands."""
    gateway = _make_gateway(session_map)
    assert await dispatch(gateway, "42", "start", "") is None
    assert await dispatch(gateway, "42", "reset", "") is None
    assert await dispatch(gateway, "42", "foobar", "") is None
