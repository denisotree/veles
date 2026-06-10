"""Direct Gemini adapter (M42) — `core.provider.Provider` against the Google GenAI SDK.

Uses `google.genai.Client.models.generate_content` (and the streaming
sibling) instead of routing through OpenRouter. Wire-shape conversion:

- System messages collapse into the `system_instruction` field of
  `GenerateContentConfig`.
- User messages map to `{"role": "user", "parts": [{"text": ...}]}`.
- Assistant text → `{"role": "model", "parts": [{"text": ...}]}`.
- Assistant tool calls → `{"role": "model", "parts": [{"function_call":
  {"name": ..., "args": {...}}}]}` (Gemini doesn't carry stable tool-call
  ids — function calls are paired with responses by name + order).
- Tool results → `{"role": "user", "parts": [{"function_response":
  {"name": ..., "response": {"content": "..."}}}]}`. Names are looked up
  from the prior assistant tool_call's `id` (Veles' `tool_call_id`),
  building an `id → name` map as conversion walks the history.
- OpenAI-shaped tool schemas (`{type:"function", function:{name, parameters}}`)
  translate to a single `{"function_declarations": [...]}` Tool entry.

Streaming via `generate_content_stream` yields chunks; each chunk's text
parts emit `TextDelta`, function-call parts accumulate into the final
ToolCalls list. Gemini emits complete function-call parts in single
chunks (not partial-arg-streamed like Anthropic), so accumulation is
straight append.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

from google import genai

from veles.adapters._wire_common import convert_openai_tools
from veles.core.provider import (
    Message,
    ProviderResponse,
    StreamEnd,
    StreamEvent,
    TextDelta,
    TokenUsage,
    ToolCall,
)

_API_KEY_ENV = "GEMINI_API_KEY"
_FALLBACK_API_KEY_ENV = "GOOGLE_API_KEY"


class GeminiProvider:
    """Provider backed by Google's GenAI Python SDK (Gemini)."""

    name: str = "gemini"
    supports_tools: bool = True
    supports_streaming: bool = True

    def __init__(
        self,
        *,
        api_key: str | None = None,
        client: genai.Client | None = None,
    ) -> None:
        if client is not None:
            self._client = client
            return
        from veles.core.provider_factory import require_api_key

        key = require_api_key("gemini", explicit=api_key)
        self._client = genai.Client(api_key=key)

    def list_models(self) -> list[str]:
        """Return Gemini model ids via `genai.Client.models.list()`.

        The SDK yields entries whose `name` looks like `"models/gemini-2.5-pro"`;
        we strip the `models/` prefix so the result is what `create_message(model=…)`
        expects. Re-raises network/auth errors — `tui.screens._model_fetcher`
        decides whether to fall back to a curated list.
        """
        ids: list[str] = []
        for m in self._client.models.list():
            raw = getattr(m, "name", "") or ""
            if raw.startswith("models/"):
                raw = raw[len("models/") :]
            if raw:
                ids.append(raw)
        return ids

    def create_message(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        *,
        model: str,
        max_tokens: int = 4096,
    ) -> ProviderResponse:
        system, contents = _split_system_and_contents(messages)
        config = _build_config(system=system, tools=tools, max_tokens=max_tokens)
        kwargs: dict[str, Any] = {"model": model, "contents": contents}
        if config:
            kwargs["config"] = config
        response = self._client.models.generate_content(**kwargs)
        return _convert_response(response)

    def stream_message(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        *,
        model: str,
        max_tokens: int = 4096,
    ) -> Iterator[StreamEvent]:
        system, contents = _split_system_and_contents(messages)
        config = _build_config(system=system, tools=tools, max_tokens=max_tokens)
        kwargs: dict[str, Any] = {"model": model, "contents": contents}
        if config:
            kwargs["config"] = config

        text_buffer = ""
        tool_calls: list[ToolCall] = []
        usage = TokenUsage()
        finish_reason: str | None = None

        for chunk in self._client.models.generate_content_stream(**kwargs):
            for cand in getattr(chunk, "candidates", None) or []:
                content = getattr(cand, "content", None)
                for part in getattr(content, "parts", None) or []:
                    text = getattr(part, "text", None)
                    if text:
                        text_buffer += text
                        yield TextDelta(text=text)
                    fc = getattr(part, "function_call", None)
                    if fc is not None:
                        tool_calls.append(
                            ToolCall(
                                id=getattr(fc, "id", "") or "",
                                name=getattr(fc, "name", "") or "",
                                arguments=dict(getattr(fc, "args", None) or {}),
                            )
                        )
                fr = getattr(cand, "finish_reason", None)
                if fr is not None:
                    finish_reason = str(fr)
            usage_meta = getattr(chunk, "usage_metadata", None)
            if usage_meta is not None:
                usage = _usage_from_meta(usage_meta)

        yield StreamEnd(
            response=ProviderResponse(
                text=text_buffer or None,
                tool_calls=tool_calls,
                usage=usage,
                finish_reason=finish_reason,
                raw=None,
            )
        )


def _split_system_and_contents(
    messages: list[Message],
) -> tuple[str | None, list[dict[str, Any]]]:
    """Convert Veles messages to Gemini's `contents` list + system_instruction.

    Tool messages need the function name (Gemini matches by name+order, not by
    id), so we walk the assistant messages first to build an `id → name` map.
    """
    tool_name_by_id: dict[str, str] = {}
    for m in messages:
        if m.role == "assistant":
            for tc in m.tool_calls:
                if tc.id:
                    tool_name_by_id[tc.id] = tc.name

    system_parts: list[str] = []
    out: list[dict[str, Any]] = []
    pending_function_responses: list[dict[str, Any]] = []

    def flush_pending() -> None:
        if pending_function_responses:
            out.append({"role": "user", "parts": list(pending_function_responses)})
            pending_function_responses.clear()

    for m in messages:
        if m.role == "system":
            if m.content:
                system_parts.append(m.content)
            continue
        if m.role == "tool":
            name = tool_name_by_id.get(m.tool_call_id or "", "tool")
            pending_function_responses.append(
                {
                    "function_response": {
                        "name": name,
                        "response": {"content": m.content or ""},
                    }
                }
            )
            continue
        flush_pending()
        if m.role == "assistant":
            parts: list[dict[str, Any]] = []
            if m.content:
                parts.append({"text": m.content})
            for tc in m.tool_calls:
                parts.append(
                    {
                        "function_call": {
                            "name": tc.name,
                            "args": tc.arguments,
                        }
                    }
                )
            if parts:
                out.append({"role": "model", "parts": parts})
        elif m.role == "user":
            out.append({"role": "user", "parts": [{"text": m.content or ""}]})
        else:
            out.append({"role": m.role, "parts": [{"text": m.content or ""}]})

    flush_pending()
    system = "\n\n".join(system_parts) if system_parts else None
    return system, out


def _build_config(
    *,
    system: str | None,
    tools: list[dict[str, Any]] | None,
    max_tokens: int,
) -> dict[str, Any]:
    config: dict[str, Any] = {"max_output_tokens": max_tokens}
    if system:
        config["system_instruction"] = system
    if tools:
        decls = _convert_tools(tools)
        if decls:
            config["tools"] = [{"function_declarations": decls}]
    return config


def _convert_tools(openai_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Translate OpenAI-shaped tool schemas to Gemini's function_declarations shape."""
    return convert_openai_tools(openai_tools, parameters_key="parameters")


def _convert_response(response: Any) -> ProviderResponse:
    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    finish_reason: str | None = None
    for cand in getattr(response, "candidates", None) or []:
        content = getattr(cand, "content", None)
        for part in getattr(content, "parts", None) or []:
            text = getattr(part, "text", None)
            if text:
                text_parts.append(text)
            fc = getattr(part, "function_call", None)
            if fc is not None:
                tool_calls.append(
                    ToolCall(
                        id=getattr(fc, "id", "") or "",
                        name=getattr(fc, "name", "") or "",
                        arguments=dict(getattr(fc, "args", None) or {}),
                    )
                )
        fr = getattr(cand, "finish_reason", None)
        if fr is not None:
            finish_reason = str(fr)
    text = "\n".join(p for p in text_parts if p) or None
    usage_meta = getattr(response, "usage_metadata", None)
    usage = _usage_from_meta(usage_meta) if usage_meta else TokenUsage()
    return ProviderResponse(
        text=text,
        tool_calls=tool_calls,
        usage=usage,
        finish_reason=finish_reason,
        raw=response,
    )


def _usage_from_meta(meta: Any) -> TokenUsage:
    prompt = getattr(meta, "prompt_token_count", 0) or 0
    completion = getattr(meta, "candidates_token_count", 0) or 0
    total = getattr(meta, "total_token_count", None)
    if total is None or total == 0:
        total = prompt + completion
    return TokenUsage(
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=total,
    )
