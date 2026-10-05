"""M116.1: slash-command dispatcher for the Telegram channel.

Unit-tests for `channels/telegram/_commands.py` — parse + dispatch +
menu payload. Handler functions are async; we use pytest-asyncio.

Integration tests (handler reached from `_handle_update`) live in
`test_channels_telegram.py` to stay alongside the rest of the
gateway suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.channels.telegram import TelegramGateway
from veles.channels.telegram._commands import (
    dispatch,
    menu_descriptors,
    parse_command,
)
from veles.core.chat_sessions import SessionMap

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


def test_a_message_that_starts_with_a_path_is_not_a_command() -> None:
    """M274: Telegram's own grammar (`[a-z0-9_]{1,32}`, checked against the
    Bot API docs) decides what is a command. Before this, a path at the start
    of a message was parsed as a command and answered "Unknown command"."""
    assert parse_command("/var/log/app.log почему падает?") is None
    assert parse_command("/Users/me/report.pdf посмотри файл") is None
    assert parse_command("/tmp") == ("tmp", "")  # a valid name is still a command
    assert parse_command("/" + "a" * 33) is None  # past Telegram's 32-char limit
    assert parse_command("/ help") is None  # Telegram has no command with a space


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


class _UsageClient:
    """Backend stub with the M116b usage and the fields /settings reads."""

    async def get_session_usage(self, session_id: str) -> dict:
        return {
            "session_id": session_id,
            "tokens_in": 1200,
            "tokens_out": 300,
            "cache_read": 50,
            "last_prompt_tokens": 25_000,
            "context_window": 100_000,
            "model": "z-ai/glm-5.3-flash",
            "since_daemon_start": True,
        }

    async def get_session(self, session_id: str) -> dict:
        return {"session_id": session_id, "mode": "default", "goal": None}

    async def health(self) -> dict:
        return {"model": "z-ai/glm-5.3-flash"}


def _usage_gateway(session_map: SessionMap) -> TelegramGateway:
    session_map.set("42", "ses-1")
    return TelegramGateway(bot_token="X", daemon_client=_UsageClient(), session_map=session_map)  # type: ignore[arg-type]


async def test_tokens_reports_the_sessions_usage(session_map: SessionMap) -> None:
    reply = await dispatch(_usage_gateway(session_map), "42", "tokens", "")
    assert reply is not None and "1200" in reply and "300" in reply and "50" in reply


async def test_context_reports_occupancy_against_the_window(session_map: SessionMap) -> None:
    reply = await dispatch(_usage_gateway(session_map), "42", "context", "")
    assert reply is not None and "25000" in reply and "100000" in reply and "25%" in reply


async def test_tokens_before_any_session_says_so(session_map: SessionMap) -> None:
    gateway = TelegramGateway(bot_token="X", daemon_client=_UsageClient(), session_map=session_map)  # type: ignore[arg-type]
    reply = await dispatch(gateway, "42", "tokens", "")
    assert reply is not None and "send a message" in reply


async def test_settings_shows_model_usage_and_mode_buttons(session_map: SessionMap) -> None:
    """M116c: one message — model (fixed by config), session, usage, mode buttons."""
    gateway = _usage_gateway(session_map)
    sent: list[dict] = []

    async def fake_send(method, payload):
        sent.append({"method": method, **payload})
        return {"message_id": 1, "chat": payload.get("chat_id")}

    gateway._telegram_send = fake_send  # type: ignore[method-assign]
    reply = await dispatch(gateway, "42", "settings", "")
    assert reply == ""
    message = next(s for s in sent if s["method"] == "sendMessage")
    body = message["text"]
    assert "z-ai/glm-5.3-flash" in body and "ses-1" in body and "1200" in body
    buttons = [b for row in message["reply_markup"]["inline_keyboard"] for b in row]
    assert buttons and all(b["callback_data"].startswith("mo:") for b in buttons)
    assert any(b["text"].startswith("✓") for b in buttons)  # the current mode is marked


async def test_settings_is_in_the_menu() -> None:
    assert "settings" in {d["command"] for d in menu_descriptors()}
    assert not any("WIP" in d["description"] for d in menu_descriptors())


class _RecordingClient:
    """Fails the test if a command sneaks a prompt into the chat's session."""

    def __init__(self, dream: dict | Exception | None = None) -> None:
        self.submitted: list[str] = []
        self.dreams = 0
        self._dream = dream

    async def submit_run(self, prompt: str, *, session_id=None, origin=None):
        self.submitted.append(prompt)
        return {"run_id": "r1", "session_id": session_id, "state": "running"}

    async def stream_events(self, run_id):
        if False:
            yield

    async def run_dream(self):
        self.dreams += 1
        if isinstance(self._dream, Exception):
            raise self._dream
        return self._dream


def _gateway_with(client: _RecordingClient, session_map: SessionMap):
    from veles.channels.telegram import TelegramGateway

    return TelegramGateway(
        bot_token="X",
        daemon_client=client,  # type: ignore[arg-type]
        session_map=session_map,
    )


async def test_dream_runs_the_dream_runner_and_reports_its_result(
    session_map: SessionMap,
) -> None:
    """M276: /dream used to send "[DREAM MODE] …" as an ordinary prompt."""
    client = _RecordingClient({"summary": "insights=2 dedup=0", "notes": ["lint <skipped>"]})
    reply = await dispatch(_gateway_with(client, session_map), "42", "dream", "")
    assert client.dreams == 1
    assert client.submitted == []
    assert reply is not None
    assert "insights=2 dedup=0" in reply
    assert "lint &lt;skipped&gt;" in reply


async def test_dream_reports_a_daemon_without_a_dream_runner(session_map: SessionMap) -> None:
    client = _RecordingClient(RuntimeError("the dream runner is not enabled on this daemon"))
    reply = await dispatch(_gateway_with(client, session_map), "42", "dream", "")
    assert reply is not None
    assert "not enabled" in reply


async def test_goal_dream_appear_in_menu_descriptors() -> None:
    from veles.channels.telegram._commands import menu_descriptors

    cmds = {d["command"] for d in menu_descriptors()}
    assert "goal" in cmds
    assert "dream" in cmds


async def test_help_lists_goal_and_dream(session_map: SessionMap) -> None:
    gateway = _make_gateway(session_map)
    reply = await dispatch(gateway, "42", "help", "")
    assert reply is not None
    assert "/goal" in reply
    assert "/dream" in reply


async def test_every_menu_command_is_dispatchable() -> None:
    """The invariant the old `all_command_names` checks were approximating:
    a command the bot publishes in its menu (`setMyCommands`) must have
    something that answers it — the dispatcher or the gateway itself. A menu
    entry with no handler is a button that does nothing."""
    from veles.channels.telegram._commands import _HANDLERS, menu_descriptors

    published = {d["command"] for d in menu_descriptors()}
    assert published - set(_HANDLERS) == set()
    assert {"goal", "dream"} <= published


async def test_dispatch_unknown_command_returns_none(session_map: SessionMap) -> None:
    gateway = _make_gateway(session_map)
    assert await dispatch(gateway, "42", "foobar", "") is None


async def test_reset_forgets_the_chat_session(session_map: SessionMap) -> None:
    gateway = _make_gateway(session_map)
    session_map.set("42", "sess-1")
    assert await dispatch(gateway, "42", "reset", "") == "History cleared."
    assert session_map.get("42") is None
    assert await dispatch(gateway, "42", "reset", "") == "History is already empty."
