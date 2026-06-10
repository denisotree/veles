"""Local-model adapters — Ollama, llama.cpp, generic OpenAI-compatible.

All three speak the OpenAI Chat Completions wire format, so a single thin
base class (`_OpenAICompatibleBase`) covers `create_message` and
`stream_message`. Each concrete provider is a small subclass that pins
default `base_url`, env-var name, and (for Ollama) backend-specific extras
like `list_models()`.

Local backends can be slow — users who connect them have opted in to that.
The base class uses a 10-minute total `request_timeout` and an httpx
per-read (i.e. per-chunk on a stream) `inactivity_timeout` so the request
lives as long as data keeps flowing.
"""

from veles.adapters.local.llamacpp import LlamaCppProvider
from veles.adapters.local.ollama import OllamaProvider
from veles.adapters.local.openai_compatible import OpenAICompatibleProvider

__all__ = ["OllamaProvider", "LlamaCppProvider", "OpenAICompatibleProvider"]
