"""Optional multimodal modules for channels and tools.

VISION §5.8 declares multimodality as a *module* surface — core
stays text-only, dedicated modules upgrade specific channels. This
package houses the canonical interfaces; concrete providers (OpenAI
Whisper for STT, GPT-4V for vision, local Whisper.cpp, etc.) ship
as adapter implementations that conform to the abstract interface.

Modules in this package:
- `stt.py` — `transcribe(audio_bytes, mime) -> str` for voice→text.
- `vision.py` — `describe_image(image_bytes, mime) -> str` for
  image→text descriptions.

Each module exposes a `get_<kind>_adapter()` factory that:
- Returns a configured adapter if one is registered globally
  (`register_<kind>_adapter(adapter)` — set up at daemon startup).
- Returns `None` if no adapter is configured.

This keeps `channels/telegram.py` (and any future Slack/web channel)
agnostic of which provider is doing the lifting: if an adapter is
present, the voice/photo gets a transcription/description fused into
the prompt; if not, the channel gracefully reports "multimodal not
configured" instead of dropping the input silently.
"""

from veles.modules.embedding import (
    EmbeddingAdapter,
    EmbeddingError,
    get_embedding_adapter,
    register_embedding_adapter,
    reset_embedding_adapter,
)
from veles.modules.embedding_autodetect import autodetect_embedding_adapter
from veles.modules.stt import (
    STTAdapter,
    get_stt_adapter,
    register_stt_adapter,
    reset_stt_adapter,
)
from veles.modules.vision import (
    VisionAdapter,
    get_vision_adapter,
    register_vision_adapter,
    reset_vision_adapter,
)

__all__ = [
    "EmbeddingAdapter",
    "EmbeddingError",
    "STTAdapter",
    "VisionAdapter",
    "autodetect_embedding_adapter",
    "get_embedding_adapter",
    "get_stt_adapter",
    "get_vision_adapter",
    "register_embedding_adapter",
    "register_stt_adapter",
    "register_vision_adapter",
    "reset_embedding_adapter",
    "reset_stt_adapter",
    "reset_vision_adapter",
]
