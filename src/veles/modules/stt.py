"""Speech-to-text adapter interface.

The abstract `STTAdapter` is a single-method protocol. Concrete
implementations live in adapter modules (e.g. `openai_whisper_adapter`,
`whisper_cpp_adapter`) — none ship in core; modules opt into a
provider by registering an adapter at daemon startup:

    from veles.modules.stt import register_stt_adapter
    from my_org.veles_stt_openai import OpenAIWhisperAdapter

    register_stt_adapter(OpenAIWhisperAdapter(api_key="..."))

Telegram (and future Slack/web channels) call `get_stt_adapter()`
when a voice message arrives. If `None`, the channel surfaces a
"multimodal not configured" notice; if an adapter is registered,
the audio bytes are transcribed and the resulting text is folded
into the agent prompt.

This module deliberately ships **no** concrete adapter — vendor
choices stay opt-in, and a stock Veles install never bundles a
cloud STT dependency.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class STTAdapter(Protocol):
    """Transcribe audio bytes into plain text. Implementations are
    free to be sync or async; the call site adapts via thread-pool
    wrapping when needed."""

    name: str

    def transcribe(self, audio_bytes: bytes, mime: str) -> str:
        """Return the transcribed text. Raises `STTError` on failure;
        the channel layer translates that into a user-visible notice."""
        ...


class STTError(RuntimeError):
    """Adapter failure (network, unsupported codec, auth, …).
    Surfaces as a polite "couldn't transcribe" message in the
    channel rather than crashing the gateway."""


_REGISTERED: STTAdapter | None = None


def register_stt_adapter(adapter: STTAdapter | None) -> None:
    """Install (or clear with None) the process-global STT adapter.
    Daemon startup is the typical caller; tests use `reset_stt_adapter`
    afterwards to keep state isolated."""
    global _REGISTERED
    _REGISTERED = adapter


def get_stt_adapter() -> STTAdapter | None:
    """Return the registered adapter, or None when multimodal STT
    isn't configured for this install."""
    return _REGISTERED


def reset_stt_adapter() -> None:
    """Test helper — clear any installed adapter so subsequent tests
    start from a clean state."""
    global _REGISTERED
    _REGISTERED = None


__all__ = [
    "STTAdapter",
    "STTError",
    "get_stt_adapter",
    "register_stt_adapter",
    "reset_stt_adapter",
]
