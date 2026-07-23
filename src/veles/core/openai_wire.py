"""Shared OpenAI Chat Completions wire-format handling.

Three adapters speak the OpenAI Chat Completions protocol:

- `adapters/openrouter.py` — OpenRouter relay (cloud, with cache hints)
- `adapters/openai_direct.py` — OpenAI native (cloud, with cache hints)
- `adapters/local/_base.py` — local model servers (no cache hints, no api key)

Before this module they all duplicated ~150 LOC of message conversion,
stream parsing, and usage extraction. The class below is the single
source of truth; adapters subclass and override two hooks:

- `_prepare_messages(messages, model)` — default returns the wire-form
  list as-is; cloud adapters override to apply Anthropic cache hints.
- `_extract_usage(usage_obj)` — default returns prompt/completion/total;
  cloud adapters override to also harvest `cache_read_tokens`.

The `_max_tokens_kwarg(model)` hook handles OpenAI's o1*/o3*/o4*/gpt-5*
quirk (those reject `max_tokens` and require `max_completion_tokens`)."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

from veles.core.provider import (
    Message,
    ProviderError,
    ProviderResponse,
    ProviderTimeout,
    ProviderUnavailable,
    ReasoningDelta,
    StreamEnd,
    StreamEvent,
    TextDelta,
    TokenUsage,
    ToolCall,
)
from veles.core.tool_args import decode_tool_args

# SDK exceptions the wire layer translates into typed veles errors with
# actionable hints (M132 + M132b). Order matters at the catch site only as
# a tuple membership test — the actual dispatch is by isinstance in
# `_translate_openai_error`, where APITimeoutError (⊂ APIConnectionError)
# is checked first.
_TRANSLATED_OPENAI_ERRORS = (APITimeoutError, APIConnectionError, APIStatusError)
_ERROR_BODY_LIMIT = 500

logger = logging.getLogger(__name__)


def _is_cache_control_error(exc: Exception) -> bool:
    """True for an upstream 400 that rejected our `cache_control` hint — the
    signal to self-heal by dropping the M220 tool-tail breakpoint and retrying.
    Matches on the error body so it fires only for the cache-hint rejection,
    not any other 400."""
    if not isinstance(exc, APIStatusError):
        return False
    if getattr(exc, "status_code", None) != 400:
        return False
    return "cache_control" in str(exc).lower()


def to_openai_message(m: Message) -> dict[str, Any]:
    """Convert one Veles Message to its OpenAI Chat Completions wire form."""
    if m.role == "tool":
        if m.tool_call_id is None:
            raise ValueError("tool message must carry tool_call_id")
        return {
            "role": "tool",
            "tool_call_id": m.tool_call_id,
            "content": m.content or "",
        }
    if m.role == "assistant" and m.tool_calls:
        return {
            "role": "assistant",
            "content": m.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in m.tool_calls
            ],
        }
    return {"role": m.role, "content": m.content or ""}


def max_tokens_kwarg_for(model: str) -> str:
    """Pick the parameter name OpenAI accepts for this model.

    Reasoning-family models (o1*, o3*, o4*, gpt-5*) reject the legacy
    `max_tokens` and require `max_completion_tokens`. Strip any leading
    provider/route prefix first — OpenRouter callers routinely pass
    qualified ids like `openai/gpt-5.x`."""
    tail = model.lower().rsplit("/", 1)[-1]
    if tail.startswith(("o1", "o3", "o4", "gpt-5")):
        return "max_completion_tokens"
    return "max_tokens"


class OpenAICompatibleProvider:
    """Base for any Provider that talks the OpenAI Chat Completions wire format.

    Subclasses build a configured `openai.OpenAI` client and pass it
    to `__init__(client=...)`, then override `_prepare_messages` and
    `_extract_usage` if they need cache-hint injection or cache-read
    token tracking."""

    name: str = "openai-compatible"
    supports_tools: bool = True
    supports_streaming: bool = True

    def __init__(self, *, client: OpenAI) -> None:
        self._client = client

    # ---- hooks subclasses may override ----

    def _max_tokens_kwarg(self, model: str) -> str:
        return max_tokens_kwarg_for(model)

    def _prepare_messages(self, messages: list[Message], model: str) -> list[dict[str, Any]]:
        """Default: plain wire-form with the cache sentinel stripped.

        Cloud adapters override to call `apply_cache_hints` (which converts
        the sentinel into `cache_control` blocks for Anthropic). The default
        — used by local backends — must still strip the sentinel so it never
        leaks into the prompt; local servers do their own automatic prefix
        KV-caching off the (now clean, stable) prefix (M178)."""
        from veles.core.cache_hints import strip_cache_sentinel

        return strip_cache_sentinel([to_openai_message(m) for m in messages])

    def _request_options(self, model: str) -> dict[str, Any]:
        """Extra kwargs merged into the `chat.completions.create` call. Empty by
        default; OpenRouter overrides to forward a sticky-routing `session_id`
        (M224) so a conversation's requests pin one provider and prompt caching
        actually hits."""
        return {}

    def _extract_usage(self, usage_obj: Any) -> TokenUsage:
        """Default: prompt/completion/total only. Cloud adapters override
        to also grab `prompt_tokens_details.cached_tokens`."""
        if usage_obj is None:
            return TokenUsage()
        return TokenUsage(
            prompt_tokens=usage_obj.prompt_tokens or 0,
            completion_tokens=usage_obj.completion_tokens or 0,
            total_tokens=usage_obj.total_tokens or 0,
        )

    def _connection_error_hint(self) -> str:
        """Actionable hint appended to a `ProviderUnavailable` message.
        Default empty (cloud providers); local adapters override to point
        at the server (e.g. `ollama serve`) and the base-URL env var."""
        return ""

    def _server_error_hint(self, status: int | str) -> str:
        """Actionable hint appended to a `ProviderError` raised from an
        upstream 4xx/5xx. Default empty; local adapters override."""
        return ""

    # ---- error translation (M132 / M132b) ----

    def _translate_openai_error(self, exc: Exception) -> Exception:
        """Map an OpenAI-SDK exception to a typed veles error with a hint.

        Returns the original exception untouched when it isn't one we
        specialise, so the caller's `raise self._translate(exc) from exc`
        re-raises faithfully. APITimeoutError is a subclass of
        APIConnectionError, so it must be tested first."""
        name = getattr(self, "name", "provider")
        base = str(getattr(self._client, "base_url", "") or "").rstrip("/")
        if isinstance(exc, APITimeoutError):
            return ProviderTimeout(str(exc) or f"{name} request timed out")
        if isinstance(exc, APIConnectionError):
            hint = self._connection_error_hint()
            msg = f"cannot reach {name} at {base or '<unknown>'}"
            return ProviderUnavailable(f"{msg} — {hint}" if hint else msg)
        if isinstance(exc, APIStatusError):
            status = getattr(exc, "status_code", "?")
            body = str(exc)
            if len(body) > _ERROR_BODY_LIMIT:
                body = body[: _ERROR_BODY_LIMIT - 1] + "…"
            hint = self._server_error_hint(status)
            msg = f"{name} returned HTTP {status}: {body}"
            return ProviderError(f"{msg} — {hint}" if hint else msg)
        return exc

    # ---- shared API surface ----

    def list_models(self) -> list[str]:
        page = self._client.models.list()
        return [m.id for m in page]

    def _call_create(self, kwargs: dict[str, Any], messages: list[Message], model: str) -> Any:
        """Run `chat.completions.create` with the M220 cache self-heal: if the
        wire rejects our `cache_control` tool-tail hint (400), drop the tool-tail
        breakpoint process-wide, re-prepare the messages, and retry once. The
        cache is a bonus — a rejection must never break an agentic turn."""
        try:
            return self._client.chat.completions.create(**kwargs)
        except _TRANSLATED_OPENAI_ERRORS as exc:
            from veles.core.cache_hints import disable_tool_tail, tool_tail_enabled

            if tool_tail_enabled() and _is_cache_control_error(exc):
                disable_tool_tail()
                logger.warning(
                    "cache_control rejected on the tool tail; disabled tool-tail "
                    "caching and retrying without it (self-healed, %s)",
                    getattr(self, "name", "provider"),
                )
                retry = {**kwargs, "messages": self._prepare_messages(messages, model)}
                try:
                    return self._client.chat.completions.create(**retry)
                except _TRANSLATED_OPENAI_ERRORS as exc2:
                    raise self._translate_openai_error(exc2) from exc2
            raise self._translate_openai_error(exc) from exc

    def create_message(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        *,
        model: str,
        max_tokens: int = 4096,
    ) -> ProviderResponse:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": self._prepare_messages(messages, model),
            self._max_tokens_kwarg(model): max_tokens,
        }
        if tools and self.supports_tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        kwargs.update(self._request_options(model))
        completion = self._call_create(kwargs, messages, model)
        choice = completion.choices[0]
        msg = choice.message
        tool_calls = _decode_tool_calls(msg.tool_calls or [])
        return ProviderResponse(
            text=msg.content,
            tool_calls=tool_calls,
            usage=self._extract_usage(completion.usage),
            finish_reason=choice.finish_reason,
            raw=completion,
        )

    def stream_message(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        *,
        model: str,
        max_tokens: int = 4096,
    ) -> Iterator[StreamEvent]:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": self._prepare_messages(messages, model),
            self._max_tokens_kwarg(model): max_tokens,
            "stream": True,
        }
        if tools and self.supports_tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        kwargs.update(self._request_options(model))

        text_buffer = ""
        tool_calls_acc: dict[int, dict[str, Any]] = {}
        tool_call_ids: dict[str, int] = {}  # id → bucket, for index-less deltas
        finish_reason: str | None = None
        usage = TokenUsage()

        # A connection failure / 5xx / timeout can fire on the initial
        # request or mid-stream (the SDK applies the read timeout per
        # chunk); translate either into a typed veles error with an
        # actionable hint so the agent + UI label it distinctly
        # (M132 timeout, M132b unavailable/server-error). The initial call
        # also carries the M220 cache self-heal (a cache_control 400 is a
        # request-validation error, so it can only surface here, not mid-stream).
        stream = self._call_create(kwargs, messages, model)

        def _chunks() -> Iterator[Any]:
            try:
                yield from stream
            except _TRANSLATED_OPENAI_ERRORS as exc:
                raise self._translate_openai_error(exc) from exc

        for chunk in _chunks():
            chunk_usage = getattr(chunk, "usage", None)
            if chunk_usage is not None:
                usage = self._extract_usage(chunk_usage)
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            delta = choice.delta
            # Reasoning tokens arrive on a separate field: OpenRouter uses
            # `reasoning`, some OpenAI-compat backends use `reasoning_content`.
            # Surface them as ReasoningDelta (M133) — kept out of the answer
            # buffer so chat shows only the final text.
            reasoning = getattr(delta, "reasoning", None) or getattr(
                delta, "reasoning_content", None
            )
            if reasoning:
                yield ReasoningDelta(text=reasoning)
            if getattr(delta, "content", None):
                yield TextDelta(text=delta.content)
                text_buffer += delta.content
            for tc_delta in getattr(delta, "tool_calls", None) or []:
                idx = getattr(tc_delta, "index", None)
                if idx is None:
                    # Some providers/models (seen live 2026-07-08: openrouter +
                    # anthropic/claude-sonnet-5) omit `index` on parallel
                    # tool-call deltas. Bucketing them all under one key would
                    # concatenate argument strings from DIFFERENT calls
                    # (`{"a":1}{"b":2}`) → JSON decode fails → `{"_raw": …}` →
                    # every tool call in the turn dies. Recover the boundaries:
                    # a delta carrying a NEW id starts a new call; an id-less
                    # delta continues the last one.
                    tc_id = getattr(tc_delta, "id", None)
                    if tc_id and tc_id in tool_call_ids:
                        idx = tool_call_ids[tc_id]
                    elif tc_id:
                        idx = (max(tool_calls_acc) + 1) if tool_calls_acc else 0
                        tool_call_ids[tc_id] = idx
                    else:
                        idx = max(tool_calls_acc) if tool_calls_acc else 0
                acc = tool_calls_acc.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                if tc_delta.id:
                    acc["id"] = tc_delta.id
                fn = getattr(tc_delta, "function", None)
                if fn is not None:
                    if getattr(fn, "name", None):
                        acc["name"] = fn.name
                    if getattr(fn, "arguments", None):
                        acc["arguments"] += fn.arguments
            if choice.finish_reason:
                finish_reason = choice.finish_reason

        tool_calls: list[ToolCall] = []
        for acc in tool_calls_acc.values():
            arguments = decode_tool_args(acc["arguments"])
            tool_calls.append(ToolCall(id=acc["id"], name=acc["name"], arguments=arguments))
        response = ProviderResponse(
            text=text_buffer or None,
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=finish_reason,
            raw=None,
        )
        yield StreamEnd(response=response)


def _decode_tool_calls(raw_calls: list[Any]) -> list[ToolCall]:
    """Decode JSON arguments on a non-streaming response's tool_calls list."""
    out: list[ToolCall] = []
    for tc in raw_calls:
        arguments = decode_tool_args(tc.function.arguments)
        out.append(ToolCall(id=tc.id, name=tc.function.name, arguments=arguments))
    return out


def extract_usage_with_cache(usage_obj: Any) -> TokenUsage:
    """Cloud-flavoured usage extractor — also harvests `cached_tokens`
    from `prompt_tokens_details`. Both openrouter and openai_direct use
    this; local adapters use the plain default."""
    if usage_obj is None:
        return TokenUsage()
    details = getattr(usage_obj, "prompt_tokens_details", None)
    cache_read = getattr(details, "cached_tokens", 0) or 0 if details else 0
    return TokenUsage(
        prompt_tokens=usage_obj.prompt_tokens or 0,
        completion_tokens=usage_obj.completion_tokens or 0,
        total_tokens=usage_obj.total_tokens or 0,
        cache_read_tokens=cache_read,
    )
