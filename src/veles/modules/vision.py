"""Vision (image → text description) adapter interface.

Parallel to `stt.py`: an abstract `VisionAdapter` protocol plus
`register_vision_adapter` / `get_vision_adapter` / `reset_vision_adapter`
for the singleton lifecycle. Concrete implementations (OpenAI
GPT-4V, Anthropic Claude vision, local LLaVA, …) ship as separate
adapter packages and register at daemon startup.

The channel call site (Telegram on photo upload, future web on file
drop) consults `get_vision_adapter()`: if registered, the photo
bytes are described into prose and the description joins the agent
prompt as text. If `None`, the user gets a "multimodal not
configured" notice instead of a silent drop.

No concrete adapter ships in core — stock Veles never bundles a
cloud vision dependency.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class VisionAdapter(Protocol):
    """Convert image bytes into a text description. Synchronous
    interface; channels wrap async calls into a thread pool when
    a particular adapter is sync-only."""

    name: str

    def describe_image(self, image_bytes: bytes, mime: str) -> str:
        """Return a prose description of `image_bytes`. Raises
        `VisionError` on failure; the channel layer translates that
        into a user-visible notice."""
        ...


class VisionError(RuntimeError):
    """Adapter failure (network, unsupported format, auth, …).
    Surfaces as a polite "couldn't describe the image" notice."""


_REGISTERED: VisionAdapter | None = None


def register_vision_adapter(adapter: VisionAdapter | None) -> None:
    """Install (or clear with None) the process-global vision
    adapter. Daemon startup is the typical caller."""
    global _REGISTERED
    _REGISTERED = adapter


def get_vision_adapter() -> VisionAdapter | None:
    """Return the registered adapter, or None when multimodal vision
    isn't configured for this install."""
    return _REGISTERED


def reset_vision_adapter() -> None:
    """Test helper — clear any installed adapter."""
    global _REGISTERED
    _REGISTERED = None


__all__ = [
    "VisionAdapter",
    "VisionError",
    "get_vision_adapter",
    "register_vision_adapter",
    "reset_vision_adapter",
]
