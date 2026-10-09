"""Local-model adapters — Ollama, llama.cpp, generic OpenAI-compatible.

All three speak the OpenAI Chat Completions wire format, so a single thin
base class (`LocalOpenAIBase`) covers `create_message` and
`stream_message`. Each concrete provider is a small subclass that pins
default `base_url`, env-var name, and (for Ollama) backend-specific extras
like `list_models()`.

Local backends can be slow — users who connect them have opted in to that.
The base class waits up to `request_timeout` (600s, `[engine]
request_timeout_s` overrides) for the next bytes: the whole response on a
one-shot call, the gap between chunks on a stream, so a streamed request
lives as long as data keeps flowing.
"""

from veles.adapters.local.llamacpp import LlamaCppProvider
from veles.adapters.local.ollama import OllamaProvider
from veles.adapters.local.openai_compatible import OpenAICompatibleProvider

__all__ = ["LlamaCppProvider", "OllamaProvider", "OpenAICompatibleProvider"]
