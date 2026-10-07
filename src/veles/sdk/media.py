"""Speech-to-text and image description adapters a channel can use."""

from __future__ import annotations

from veles.modules.stt import STTError, get_stt_adapter
from veles.modules.vision import VisionError, get_vision_adapter

__all__ = ["STTError", "VisionError", "get_stt_adapter", "get_vision_adapter"]
