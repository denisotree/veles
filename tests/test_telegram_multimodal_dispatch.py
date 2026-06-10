"""Voice/photo dispatch: STT/Vision adapter call → text folded into
agent prompt; no adapter → polite "not configured" notice.

The download path (`_download_telegram_file`) is mocked — we don't
hit the actual Telegram Bot API. The STT/Vision adapters are stub
implementations that record what they got and return canned text."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from veles.channels.session_map import SessionMap
from veles.channels.telegram import TelegramGateway
from veles.modules import (
    register_stt_adapter,
    register_vision_adapter,
    reset_stt_adapter,
    reset_vision_adapter,
)
from veles.modules.stt import STTError
from veles.modules.vision import VisionError


@pytest.fixture(autouse=True)
def _isolate_adapters():
    reset_stt_adapter()
    reset_vision_adapter()
    yield
    reset_stt_adapter()
    reset_vision_adapter()


@pytest.fixture()
def session_map(tmp_path: Path) -> SessionMap:
    return SessionMap.load(tmp_path / "telegram-sessions.json")


class _StubSTT:
    name = "stub-stt"

    def __init__(self, *, fixed: str = "hello world") -> None:
        self._fixed = fixed
        self.calls: list[tuple[bytes, str]] = []

    def transcribe(self, audio_bytes: bytes, mime: str) -> str:
        self.calls.append((audio_bytes, mime))
        return self._fixed


class _StubVision:
    name = "stub-vision"

    def __init__(self, *, fixed: str = "a cat sitting on a mat") -> None:
        self._fixed = fixed
        self.calls: list[tuple[bytes, str]] = []

    def describe_image(self, image_bytes: bytes, mime: str) -> str:
        self.calls.append((image_bytes, mime))
        return self._fixed


class _CapturingClient:
    """Daemon-client stub that records every submit_run call.
    `submitted` is the captured list; tests read it directly off
    the client (TelegramGateway is slot-based dataclass, can't grow
    new attributes)."""

    def __init__(self) -> None:
        self.submitted: list[tuple[str, str | None]] = []

    async def submit_run(self, prompt: str, *, session_id=None):
        self.submitted.append((prompt, session_id))
        return {"run_id": "r1", "session_id": session_id, "state": "running"}

    async def stream_events(self, run_id):  # noqa: ARG002
        if False:
            yield


def _make_gateway(
    session_map: SessionMap, sends: list[tuple[str, dict[str, Any]]]
) -> tuple[TelegramGateway, _CapturingClient]:
    client = _CapturingClient()

    async def stub_send(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        sends.append((method, payload))
        if method == "sendMessage":
            return {"message_id": 99, "chat": payload["chat_id"]}
        if method == "editMessageText":
            return {"edited": True, "message_id": payload["message_id"]}
        if method == "sendChatAction":
            return {"ok": True}
        return {}

    gateway = TelegramGateway(
        bot_token="X",
        daemon_client=client,  # type: ignore[arg-type]
        session_map=session_map,
    )
    gateway._telegram_send = stub_send
    return gateway, client


# ---- voice path ----


async def test_voice_without_adapter_sends_notice(session_map: SessionMap) -> None:
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway, client = _make_gateway(session_map, sends)
    msg = {
        "voice": {
            "file_id": "AwACAg",
            "duration": 2,
            "file_size": 10000,
            "mime_type": "audio/ogg",
        }
    }
    await gateway._dispatch_messages(chat_id=42, chat_key="42", messages=[msg])

    # One notice sent; no agent run started
    notices = [
        p["text"]
        for m, p in sends
        if m == "sendMessage" and "no speech-to-text" in p.get("text", "")
    ]
    assert notices, f"expected STT-not-configured notice, sends={sends}"
    assert client.submitted == []  # type: ignore[attr-defined]


async def test_voice_with_adapter_transcribes_and_submits(
    session_map: SessionMap, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = _StubSTT(fixed="привет, мир")
    register_stt_adapter(adapter)
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway, client = _make_gateway(session_map, sends)

    # Mock the file download — return canned bytes. Unbound method
    # signature (`self, file_id, expected_size`) for class-level patch.
    async def fake_download(self, file_id: str, expected_size: int) -> bytes:  # noqa: ARG001
        return b"\x00fake-audio\xff"

    monkeypatch.setattr(TelegramGateway, "_download_telegram_file", fake_download)

    msg = {
        "voice": {
            "file_id": "AwACAg",
            "duration": 2,
            "file_size": 100,
            "mime_type": "audio/ogg",
        }
    }
    await gateway._dispatch_messages(chat_id=42, chat_key="42", messages=[msg])

    # Adapter saw the bytes
    assert len(adapter.calls) == 1
    audio, mime = adapter.calls[0]
    assert audio == b"\x00fake-audio\xff"
    assert mime == "audio/ogg"

    # Agent received the transcript as part of the prompt
    assert client.submitted, "expected one submit_run call"  # type: ignore[attr-defined]
    prompt, _ = client.submitted[0]  # type: ignore[attr-defined]
    assert "[voice transcript]" in prompt
    assert "привет, мир" in prompt


async def test_voice_with_caption_combines(
    session_map: SessionMap, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Voice + caption: both fold into the prompt (transcript first,
    caption second — matches arrival order)."""
    register_stt_adapter(_StubSTT(fixed="hello"))
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway, client = _make_gateway(session_map, sends)

    async def fake_download(self, *_a, **_kw):  # noqa: ARG001
        return b"audio"

    monkeypatch.setattr(TelegramGateway, "_download_telegram_file", fake_download)

    msg = {
        "voice": {"file_id": "x", "duration": 1, "mime_type": "audio/ogg"},
        "caption": "follow up: clarify A vs B",
    }
    await gateway._dispatch_messages(chat_id=42, chat_key="42", messages=[msg])

    prompt, _ = client.submitted[0]  # type: ignore[attr-defined]
    assert "hello" in prompt
    assert "clarify A vs B" in prompt


async def test_voice_adapter_failure_sends_friendly_notice(
    session_map: SessionMap, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _Flaky:
        name = "flaky"

        def transcribe(self, audio_bytes: bytes, mime: str) -> str:
            raise STTError("quota exhausted")

    register_stt_adapter(_Flaky())
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway, client = _make_gateway(session_map, sends)

    async def fake_download(self, *_a, **_kw):  # noqa: ARG001
        return b"audio"

    monkeypatch.setattr(TelegramGateway, "_download_telegram_file", fake_download)

    msg = {"voice": {"file_id": "x", "duration": 1, "mime_type": "audio/ogg"}}
    await gateway._dispatch_messages(chat_id=42, chat_key="42", messages=[msg])

    notices = [
        p["text"]
        for m, p in sends
        if m == "sendMessage" and "couldn&#x27;t transcribe" in p.get("text", "")
        or m == "sendMessage" and "couldn't transcribe" in p.get("text", "")
    ]
    assert notices
    assert client.submitted == []  # type: ignore[attr-defined]


async def test_voice_too_large_skipped(session_map: SessionMap) -> None:
    register_stt_adapter(_StubSTT())
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway, client = _make_gateway(session_map, sends)

    msg = {
        "voice": {
            "file_id": "x",
            "duration": 600,
            "file_size": 50 * 1024 * 1024,  # 50 MB, well over the 5 MB cap
            "mime_type": "audio/ogg",
        }
    }
    await gateway._dispatch_messages(chat_id=42, chat_key="42", messages=[msg])

    notices = [
        p["text"] for m, p in sends if m == "sendMessage" and "too large" in p.get("text", "")
    ]
    assert notices
    assert client.submitted == []  # type: ignore[attr-defined]


# ---- photo path ----


async def test_photo_without_adapter_sends_notice(session_map: SessionMap) -> None:
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway, client = _make_gateway(session_map, sends)

    msg = {
        "photo": [
            {"file_id": "small", "width": 90, "height": 90, "file_size": 1000},
            {"file_id": "large", "width": 1280, "height": 1280, "file_size": 200_000},
        ]
    }
    await gateway._dispatch_messages(chat_id=42, chat_key="42", messages=[msg])

    notices = [
        p["text"]
        for m, p in sends
        if m == "sendMessage" and "no vision adapter" in p.get("text", "")
    ]
    assert notices
    assert client.submitted == []  # type: ignore[attr-defined]


async def test_photo_picks_largest_variant(
    session_map: SessionMap, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Telegram's photo variants come small-to-large; we should pick
    the largest to give the vision model maximum detail."""
    adapter = _StubVision(fixed="bright sunset over mountains")
    register_vision_adapter(adapter)
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway, client = _make_gateway(session_map, sends)

    downloaded_file_ids: list[str] = []

    async def fake_download(self, file_id: str, expected_size: int) -> bytes:  # noqa: ARG001
        downloaded_file_ids.append(file_id)
        return b"\xff\xd8\xff" + b"image"

    monkeypatch.setattr(TelegramGateway, "_download_telegram_file", fake_download)

    msg = {
        "photo": [
            {"file_id": "small", "width": 90, "file_size": 1000},
            {"file_id": "medium", "width": 320, "file_size": 10_000},
            {"file_id": "large", "width": 1280, "file_size": 200_000},
        ]
    }
    await gateway._dispatch_messages(chat_id=42, chat_key="42", messages=[msg])

    # Largest variant was downloaded
    assert downloaded_file_ids == ["large"]
    # Description folded into prompt
    prompt, _ = client.submitted[0]  # type: ignore[attr-defined]
    assert "[photo description]" in prompt
    assert "sunset" in prompt


async def test_photo_with_caption_combines(
    session_map: SessionMap, monkeypatch: pytest.MonkeyPatch
) -> None:
    register_vision_adapter(_StubVision(fixed="a cat"))
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway, client = _make_gateway(session_map, sends)

    async def fake_download(self, *_a, **_kw):  # noqa: ARG001
        return b"img"

    monkeypatch.setattr(TelegramGateway, "_download_telegram_file", fake_download)

    msg = {
        "photo": [{"file_id": "x", "file_size": 10000}],
        "caption": "identify the breed",
    }
    await gateway._dispatch_messages(chat_id=42, chat_key="42", messages=[msg])

    prompt, _ = client.submitted[0]  # type: ignore[attr-defined]
    assert "a cat" in prompt
    assert "identify the breed" in prompt


async def test_vision_failure_sends_friendly_notice(
    session_map: SessionMap, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _Flaky:
        name = "flaky"

        def describe_image(self, image_bytes: bytes, mime: str) -> str:
            raise VisionError("model not loaded")

    register_vision_adapter(_Flaky())
    sends: list[tuple[str, dict[str, Any]]] = []
    gateway, client = _make_gateway(session_map, sends)

    async def fake_download(self, *_a, **_kw):  # noqa: ARG001
        return b"img"

    monkeypatch.setattr(TelegramGateway, "_download_telegram_file", fake_download)

    msg = {"photo": [{"file_id": "x", "file_size": 1000}]}
    await gateway._dispatch_messages(chat_id=42, chat_key="42", messages=[msg])

    notices = [
        p["text"]
        for m, p in sends
        if m == "sendMessage" and "couldn't describe" in p.get("text", "")
        or m == "sendMessage" and "couldn&#x27;t describe" in p.get("text", "")
    ]
    assert notices
    assert client.submitted == []  # type: ignore[attr-defined]
