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

import logging
from typing import Any

from openai import OpenAI

from veles.core.openai_wire import CloudOpenAIProvider

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_DEFAULT_REFERER = "https://github.com/denisotree/veles"
_DEFAULT_TITLE = "Veles"

_logger = logging.getLogger(__name__)


class OpenRouterProvider(CloudOpenAIProvider):
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
        timeout: float | None = None,
        model: str | None = None,
        max_retries: int | None = None,
    ) -> None:
        """M266: both client budgets are resolved here, not by the caller.

        The provider is built in three places — `provider_factory`, the CLI
        runtime, and `adapters/cli/mcp_server.py` — and only the first two
        passed a timeout, so the MCP path ran on a flat 120s regardless of the
        model. Resolving inside the constructor closes that hole and any fourth
        one: `timeout` is now `None` ("decide for me") rather than a third
        hardcoded default that silently outranked `model_budgets`.
        """
        from veles.core.model_budgets import resolve_max_retries, resolve_request_timeout
        from veles.core.provider_factory import require_api_key

        key = require_api_key("openrouter", explicit=api_key)
        kwargs: dict[str, Any] = {
            "api_key": key,
            "base_url": base_url,
            "default_headers": {
                "HTTP-Referer": referer,
                "X-Title": title,
            },
            "timeout": resolve_request_timeout(model, explicit=timeout),
        }
        retries = resolve_max_retries(explicit=max_retries)
        if retries is not None:
            # Unset means the SDK's own default, whatever it currently is —
            # don't freeze today's value into Veles.
            kwargs["max_retries"] = retries
        super().__init__(client=OpenAI(**kwargs))

    def list_models(self) -> list[str]:
        """Ids, and — for free — the catalogue behind them (M267).

        `/model` and `veles models` come through here anyway, so the round trip
        that already happened warms the metadata cache too. Without this the
        first headless `veles run` in a day pays a 3s lookup of its own.
        """
        from veles.core.model_metadata import refresh_cache

        page = list(self._client.models.list())
        try:
            refresh_cache({"data": [m.model_dump() for m in page]})
        except Exception as exc:  # a listing must never fail over its side effect
            _logger.debug("could not refresh model metadata: %s", exc)
        return [m.id for m in page]

    def _request_options(self, model: str) -> dict[str, Any]:
        """M224: forward the running turn's memory session id as OpenRouter's
        `session_id` sticky-routing key, so every request in a conversation pins
        one provider and the prompt cache (M42b/M178/M220) actually hits instead
        of scattering across backends. Uses OpenRouter's own routing — no
        hardcoded provider pin — so availability/fallback are preserved. None
        outside a persisted run → OpenRouter falls back to hashing the opening
        messages (still sticky, just not from message one).

        M250: merged on top of whatever `[engine.request.openrouter]` declares,
        via `setdefault` — an explicitly configured key wins, because that
        section is a verbatim passthrough and the user's intent is the point of
        it. Sticky routing and a hard pin are complementary: the pin narrows
        which backends are eligible, `session_id` keeps one turn on whichever
        of them answered first."""
        from veles.core.context import current_session_id

        options = super()._request_options(model)
        sid = current_session_id()
        if not sid:
            return options
        extra = dict(options.get("extra_body") or {})
        extra.setdefault("session_id", sid[:256])
        options["extra_body"] = extra
        return options
