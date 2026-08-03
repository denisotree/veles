"""M225b — Telegram's own relay markers drive the aggregation window.

A forward (`forward_origin` / `forward_from*`) or an album item
(`media_group_id`) says the user is relaying something from elsewhere and
the comment that frames it is still being typed. Those bursts get a wider
debounce window than a plain typed message, so post + post + "сохрани это"
reach the model as one turn instead of three.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from veles.channels.session_map import SessionMap
from veles.channels.telegram import TelegramGateway
from veles.channels.telegram._buffer import (
    _DEBOUNCE_SECONDS,
    _FORWARD_DEBOUNCE_SECONDS,
    _ChatBuffer,
    _is_relayed,
)


@pytest.fixture()
def session_map(tmp_path: Path) -> SessionMap:
    return SessionMap.load(tmp_path / "telegram-sessions.json")


class _Backend:
    def __init__(self) -> None:
        self.submitted: list[str] = []

    async def submit_run(self, prompt: str, *, session_id=None, origin=None):
        self.submitted.append(prompt)
        return {"run_id": "r1", "session_id": session_id}

    async def stream_events(self, run_id):
        if False:
            yield


def _make_gateway(session_map: SessionMap, **kwargs: Any) -> TelegramGateway:
    async def stub_send(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"message_id": 99}

    gateway = TelegramGateway(
        bot_token="X",
        daemon_client=_Backend(),  # type: ignore[arg-type]
        session_map=session_map,
        **kwargs,
    )
    gateway._telegram_send = stub_send
    return gateway


@pytest.mark.parametrize(
    "message,expected",
    [
        ({"text": "hi"}, False),
        ({"text": "post", "forward_origin": {"type": "channel"}}, True),
        ({"text": "post", "forward_from_chat": {"title": "Chan"}}, True),
        ({"text": "post", "forward_sender_name": "Someone"}, True),
        ({"photo": [{"file_id": "x"}], "media_group_id": "123"}, True),
    ],
)
def test_relay_markers(message: dict[str, Any], expected: bool) -> None:
    assert _is_relayed(message) is expected


def test_window_widens_once_something_relayed_lands(session_map: SessionMap) -> None:
    gateway = _make_gateway(session_map)
    buf = _ChatBuffer(chat_id=42, chat_key="42")
    assert gateway._window_for(buf) == _DEBOUNCE_SECONDS
    buf.relayed = True
    assert gateway._window_for(buf) == _FORWARD_DEBOUNCE_SECONDS


def test_windows_are_configurable(session_map: SessionMap) -> None:
    gateway = _make_gateway(session_map, debounce_seconds=0.5, forward_debounce_seconds=30.0)
    buf = _ChatBuffer(chat_id=42, chat_key="42")
    assert gateway._window_for(buf) == 0.5
    buf.relayed = True
    assert gateway._window_for(buf) == 30.0


async def test_trailing_comment_keeps_the_wide_window(session_map: SessionMap) -> None:
    """The comment closing a forward burst is plain text — the flag has
    to stay sticky, or the window would snap back to the short one and
    split the thought the user was assembling."""
    gateway = _make_gateway(session_map)
    await gateway._enqueue("42", 42, {"text": "post", "forward_from_chat": {"title": "Chan"}})
    await gateway._enqueue("42", 42, {"text": "сохрани это"})
    buf = gateway._buffers["42"]
    assert buf.relayed is True
    assert gateway._window_for(buf) == _FORWARD_DEBOUNCE_SECONDS
    buf.cancel_timer()


async def test_album_items_group(session_map: SessionMap) -> None:
    gateway = _make_gateway(session_map)
    for i in range(3):
        await gateway._enqueue(
            "42", 42, {"photo": [{"file_id": f"p{i}"}], "media_group_id": "album-1"}
        )
    buf = gateway._buffers["42"]
    assert len(buf.messages) == 3  # no early flush at the plain cap
    assert buf.relayed is True
    buf.cancel_timer()


async def test_forwarded_photo_keeps_its_attribution(
    session_map: SessionMap, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A forwarded photo takes the photo branch, which used to drop the
    `↪️ Forwarded from` line — the agent then read the image as the
    user's own."""
    gateway = _make_gateway(session_map)
    gateway.attachment_dir = tmp_path / ".veles" / "tmp"
    gateway.project_root = tmp_path

    async def fake_download(self, *_a, **_kw):
        return b"\xff\xd8\xffjpeg"

    monkeypatch.setattr(TelegramGateway, "_download_telegram_file", fake_download)
    await gateway._dispatch_messages(
        chat_id=42,
        chat_key="42",
        messages=[
            {
                "photo": [{"file_id": "large", "file_size": 9000}],
                "caption": "polezno",
                "forward_from_chat": {"title": "xor_journal"},
            }
        ],
    )
    prompt = gateway.daemon_client.submitted[0]  # type: ignore[attr-defined]
    assert "↪️ Forwarded from xor_journal:" in prompt
    assert "polezno" in prompt
