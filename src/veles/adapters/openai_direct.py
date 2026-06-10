"""Direct OpenAI adapter (M42) — `core.provider.Provider` against api.openai.com.

Same wire format as `OpenRouterProvider` (the OpenAI Chat Completions API),
but talks directly to OpenAI's own endpoint with `OPENAI_API_KEY`. Use this
when the user has direct OpenAI keys and doesn't want the OpenRouter relay.
Models are addressed by their bare OpenAI name (e.g. `gpt-4o-mini`,
`gpt-4.1`), without the `<provider>/` slash prefix that OpenRouter requires.

Cache-hint sentinel handling is preserved by reusing `apply_cache_hints`,
even though OpenAI-direct Anthropic models don't apply (the helper is a
no-op for non-Anthropic models and strips the sentinel cleanly).

Wire-format handling (message conversion, stream parsing, max_tokens
quirk) lives in `core/openai_wire.py` and is shared with OpenRouter +
local-model adapters."""

from __future__ import annotations

from typing import Any

from openai import OpenAI

from veles.core.cache_hints import apply_cache_hints
from veles.core.openai_wire import (
    OpenAICompatibleProvider,
    extract_usage_with_cache,
    max_tokens_kwarg_for,
    to_openai_message,
)
from veles.core.provider import Message, TokenUsage

_OPENAI_BASE_URL = "https://api.openai.com/v1"
_API_KEY_ENV = "OPENAI_API_KEY"


# Re-exported for tests that import the function from this module.
_to_openai_message = to_openai_message
_max_tokens_kwarg_for = max_tokens_kwarg_for


class OpenAIProvider(OpenAICompatibleProvider):
    """Provider backed by OpenAI's native Chat Completions endpoint."""

    name: str = "openai"
    supports_tools: bool = True
    supports_streaming: bool = True

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = _OPENAI_BASE_URL,
        timeout: float = 120.0,
        client: OpenAI | None = None,
    ) -> None:
        if client is not None:
            super().__init__(client=client)
            return
        from veles.core.provider_factory import require_api_key

        key = require_api_key("openai", explicit=api_key)
        super().__init__(
            client=OpenAI(api_key=key, base_url=base_url, timeout=timeout)
        )

    def _prepare_messages(
        self, messages: list[Message], model: str
    ) -> list[dict[str, Any]]:
        return apply_cache_hints(
            [to_openai_message(m) for m in messages], model
        )

    def _extract_usage(self, usage_obj: Any) -> TokenUsage:
        return extract_usage_with_cache(usage_obj)
