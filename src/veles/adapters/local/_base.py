"""Shared OpenAI-compatible Provider base for local-model adapters.

Local-model adapters (ollama, llamacpp, openai-compat) talk the OpenAI
Chat Completions wire format but with different defaults than the cloud
adapters:

- **No API key required.** Local servers don't authenticate; we pass a
  placeholder string because the OpenAI SDK refuses an empty `api_key`.
- **Generous timeouts.** Default 10-minute total request timeout, with an
  httpx per-read timeout (`inactivity_timeout`) — on a streamed response
  that means "time between chunks", so a slow local model can run for as
  long as it keeps emitting tokens.
- **No `apply_cache_hints`.** Prompt-cache sentinels are an Anthropic
  feature surfaced through OpenRouter; local backends have nothing to do
  with them.
- **`supports_tools` is opt-in.** Many open-weights models don't speak
  OpenAI tool-call format reliably; default is `False`, the user toggles
  it explicitly per session/provider.
- **Uses `max_tokens` for everything.** Local backends don't have the
  o1*/o3* quirk that requires `max_completion_tokens`, so we override
  the hook to always return `max_tokens`."""

from __future__ import annotations

import os
from typing import ClassVar

import httpx
from openai import OpenAI

from veles.core.context import expects_strict_json
from veles.core.openai_wire import (
    OpenAICompatibleProvider,
    to_openai_message,
)

# Re-export for tests that import the function from this module.
_to_openai_message = to_openai_message

# M239 self-heal, mirroring `cache_hints.disable_tool_tail`: `response_format`
# is a bonus, so a backend that rejects it must degrade instead of failing the
# turn. `VELES_LOCAL_JSON_MODE=0` disables it up front; the first 400 naming the
# parameter disables it for the rest of the process and the request is retried.
_JSON_MODE_ENABLED: bool = os.environ.get("VELES_LOCAL_JSON_MODE", "1").strip().lower() not in (
    "0",
    "false",
    "no",
)


def json_mode_enabled() -> bool:
    return _JSON_MODE_ENABLED


def disable_json_mode() -> None:
    global _JSON_MODE_ENABLED
    _JSON_MODE_ENABLED = False


def _reset_json_mode_for_tests() -> None:
    global _JSON_MODE_ENABLED
    _JSON_MODE_ENABLED = True


class _OpenAICompatibleBase(OpenAICompatibleProvider):
    """Provider implementation against any OpenAI Chat Completions endpoint."""

    name: str = "openai-compatible"
    supports_streaming: bool = True
    supports_tools: bool = False

    DEFAULT_BASE_URL: ClassVar[str] = ""
    BASE_URL_ENV: ClassVar[str | None] = None

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str = "local",
        request_timeout: float = 600.0,
        inactivity_timeout: float = 120.0,
        connect_timeout: float = 10.0,
        enable_tools: bool = False,
        client: OpenAI | None = None,
    ) -> None:
        if client is not None:
            super().__init__(client=client)
            self.supports_tools = enable_tools
            return

        url = (
            base_url
            or (os.environ.get(self.BASE_URL_ENV) if self.BASE_URL_ENV else None)
            or self.DEFAULT_BASE_URL
        )
        if not url:
            raise RuntimeError(
                f"{self.name}: base_url is required (pass base_url= or set "
                f"{self.BASE_URL_ENV} env var)"
            )

        http = httpx.Client(
            timeout=httpx.Timeout(
                connect=connect_timeout,
                read=inactivity_timeout,
                write=connect_timeout,
                pool=None,
            )
        )
        super().__init__(
            client=OpenAI(
                api_key=api_key,
                base_url=url,
                timeout=request_timeout,
                http_client=http,
                # M132b: a down local server (closed port) should fail
                # *immediately* with a clear `ProviderUnavailable`, not after
                # the SDK's default retry/backoff — that retry loop is what
                # made veles appear to "silently hang" on a closed port.
                # Local servers don't recover within a retry window anyway.
                max_retries=0,
            )
        )
        self.supports_tools = enable_tools

    # ---- error hints (M132b) ----

    def _connection_error_hint(self) -> str:
        env = f" (override the URL with {self.BASE_URL_ENV})" if self.BASE_URL_ENV else ""
        return f"is the local {self.name} server running and reachable?{env}"

    def _max_tokens_kwarg(self, model: str) -> str:
        # Local backends don't have the OpenAI reasoning-model quirk;
        # always use `max_tokens` regardless of model id.
        return "max_tokens"

    # ---- structured output (M239) ----

    def _request_options(self, model: str) -> dict[str, object]:
        """Ask for a JSON object when the caller declared it needs one.

        Small open-weight models fail structured output far more often than they
        fail the reasoning behind it, and Veles' only defence was re-prompting
        (`_PARSE_NUDGE_LIMIT`) — a wasted round trip each time. ollama and
        llama.cpp's server both honour OpenAI's `response_format`, and both
        constrain decoding rather than merely asking nicely.

        Deliberately NOT applied to every call: the fenced-tools path has the
        model emit ```veles-tool blocks inside prose, which `json_object` would
        forbid outright. Only `strict_json_mode()` callers opt in.
        """
        del model
        if not json_mode_enabled() or not expects_strict_json():
            return {}
        return {"response_format": {"type": "json_object"}}
