"""Multimodal STT / Vision adapter registry tests.

The modules ship the registry + protocol; concrete adapters are
opt-in vendor packages. These tests verify the singleton lifecycle
and Protocol conformance against tiny stub adapters.
"""

from __future__ import annotations

import pytest

from veles.modules import (
    STTAdapter,
    VisionAdapter,
    get_stt_adapter,
    get_vision_adapter,
    register_stt_adapter,
    register_vision_adapter,
    reset_stt_adapter,
    reset_vision_adapter,
)
from veles.modules.stt import STTError
from veles.modules.vision import VisionError


@pytest.fixture(autouse=True)
def _isolate_adapters():
    """Each test starts with no adapter installed and leaves none
    behind — keeps the process-global state from leaking across."""
    reset_stt_adapter()
    reset_vision_adapter()
    yield
    reset_stt_adapter()
    reset_vision_adapter()


# ---- STT ----


class _StubSTT:
    name = "stub-stt"

    def __init__(self, *, fixed_reply: str = "hello world") -> None:
        self._reply = fixed_reply
        self.calls: list[tuple[bytes, str]] = []

    def transcribe(self, audio_bytes: bytes, mime: str) -> str:
        self.calls.append((audio_bytes, mime))
        return self._reply


def test_no_stt_by_default() -> None:
    assert get_stt_adapter() is None


def test_register_returns_via_getter() -> None:
    adapter = _StubSTT()
    register_stt_adapter(adapter)
    assert get_stt_adapter() is adapter


def test_register_none_clears() -> None:
    register_stt_adapter(_StubSTT())
    register_stt_adapter(None)
    assert get_stt_adapter() is None


def test_reset_helper_clears() -> None:
    register_stt_adapter(_StubSTT())
    reset_stt_adapter()
    assert get_stt_adapter() is None


def test_stub_satisfies_protocol() -> None:
    adapter = _StubSTT()
    assert isinstance(adapter, STTAdapter)


def test_transcribe_called_through_adapter() -> None:
    adapter = _StubSTT(fixed_reply="привет, мир")
    register_stt_adapter(adapter)
    got = get_stt_adapter()
    assert got is not None
    result = got.transcribe(b"\x00\x01\x02", "audio/ogg")
    assert result == "привет, мир"
    assert adapter.calls == [(b"\x00\x01\x02", "audio/ogg")]


def test_stt_error_can_be_raised_and_caught() -> None:
    """Channels catch STTError specifically — verify it's a real
    Exception subclass and importable from the module surface."""
    with pytest.raises(STTError) as ei:
        raise STTError("transcription quota exhausted")
    assert "quota" in str(ei.value)


# ---- Vision ----


class _StubVision:
    name = "stub-vision"

    def __init__(self, *, fixed_reply: str = "a cat sitting") -> None:
        self._reply = fixed_reply
        self.calls: list[tuple[bytes, str]] = []

    def describe_image(self, image_bytes: bytes, mime: str) -> str:
        self.calls.append((image_bytes, mime))
        return self._reply


def test_no_vision_by_default() -> None:
    assert get_vision_adapter() is None


def test_vision_register_and_getter() -> None:
    adapter = _StubVision()
    register_vision_adapter(adapter)
    assert get_vision_adapter() is adapter


def test_vision_register_none_clears() -> None:
    register_vision_adapter(_StubVision())
    register_vision_adapter(None)
    assert get_vision_adapter() is None


def test_vision_stub_satisfies_protocol() -> None:
    adapter = _StubVision()
    assert isinstance(adapter, VisionAdapter)


def test_describe_image_called_through_adapter() -> None:
    adapter = _StubVision(fixed_reply="bright sunset over mountains")
    register_vision_adapter(adapter)
    got = get_vision_adapter()
    assert got is not None
    result = got.describe_image(b"\xff\xd8\xff", "image/jpeg")
    assert "sunset" in result
    assert adapter.calls == [(b"\xff\xd8\xff", "image/jpeg")]


def test_vision_error_subclass() -> None:
    with pytest.raises(VisionError):
        raise VisionError("model not loaded")


# ---- isolation ----


def test_stt_and_vision_registers_independent() -> None:
    register_stt_adapter(_StubSTT())
    register_vision_adapter(_StubVision())
    assert get_stt_adapter() is not None
    assert get_vision_adapter() is not None
    reset_stt_adapter()
    assert get_stt_adapter() is None
    # Vision still registered
    assert get_vision_adapter() is not None
