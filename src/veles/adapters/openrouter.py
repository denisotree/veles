"""OpenRouter adapter implementing core.provider.Provider.

OpenRouter exposes an OpenAI-compatible Chat Completions API, so we use the
official `openai` SDK with a custom `base_url`. Models are addressed as
`<provider>/<model>` (e.g. `anthropic/claude-sonnet-4.6`). Optional
`HTTP-Referer` / `X-Title` headers help with traffic attribution per OpenRouter
etiquette.

Wire-format handling (message conversion, stream parsing, max_tokens
quirk) lives in `core/openai_wire.py` and is shared with the direct
OpenAI adapter + local-model adapters."""

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

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_DEFAULT_REFERER = "https://github.com/denisotree/veles"
_DEFAULT_TITLE = "Veles"


# Re-exported for tests that import the function from this module.
_to_openai_message = to_openai_message
_max_tokens_kwarg_for = max_tokens_kwarg_for


class OpenRouterProvider(OpenAICompatibleProvider):
    """Provider backed by OpenRouter's OpenAI-compatible endpoint."""

    name: str = "openrouter"
    supports_tools: bool = True
    supports_streaming: bool = True

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = _OPENROUTER_BASE_URL,
        referer: str = _DEFAULT_REFERER,
        title: str = _DEFAULT_TITLE,
        timeout: float = 120.0,
    ) -> None:
        from veles.core.provider_factory import require_api_key

        key = require_api_key("openrouter", explicit=api_key)
        client = OpenAI(
            api_key=key,
            base_url=base_url,
            default_headers={
                "HTTP-Referer": referer,
                "X-Title": title,
            },
            timeout=timeout,
        )
        super().__init__(client=client)

    def _prepare_messages(
        self, messages: list[Message], model: str
    ) -> list[dict[str, Any]]:
        return apply_cache_hints(
            [to_openai_message(m) for m in messages], model
        )

    def _extract_usage(self, usage_obj: Any) -> TokenUsage:
        return extract_usage_with_cache(usage_obj)
