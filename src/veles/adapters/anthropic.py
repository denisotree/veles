"""Direct Anthropic adapter (M42) — `core.provider.Provider` against api.anthropic.com.

Talks to Anthropic's native Messages API (`client.messages.create`) instead
of routing through OpenRouter's OpenAI-compatible relay. Wire format:

- System messages collapse into a `system=` string parameter.
- Tool calls are `tool_use` content blocks (`{type, id, name, input}`).
- Tool results are `tool_result` content blocks inside a `user` message
  (`{type, tool_use_id, content}`); consecutive Veles tool messages merge
  into a single user message with multiple `tool_result` blocks since
  Anthropic enforces user/assistant alternation.
- OpenAI-shaped tool schemas (`{type:"function", function:{name,parameters}}`)
  are translated to Anthropic's `{name, description, input_schema}`.

Streaming reads `MessageStreamEvent` objects from the SDK iterator and
emits `TextDelta` events on `text_delta` blocks; tool-use input arrives
as `input_json_delta` chunks accumulated per content block.

Native prompt-caching via `cache_control` blocks (M42b): the
M35 sentinel inserted between the stable AGENTS.md+INDEX.md prefix
and the dynamic memory-context block is now honored here, not only by
the OpenRouter relay. `_split_system_and_messages` joins all system
parts, then `build_anthropic_system_blocks` turns the result into
either a plain string (no sentinel — pass through) or a content-block
list with `cache_control: {"type": "ephemeral"}` on the stable
prefix. Anthropic charges a write fee on the first turn and gives a
~90% input-token discount on every cached read after.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from anthropic import Anthropic

from veles.adapters._wire_common import convert_openai_tools
from veles.core.cache_hints import build_anthropic_system_blocks
from veles.core.provider import (
    Message,
    ProviderResponse,
    ReasoningDelta,
    StreamEnd,
    StreamEvent,
    TextDelta,
    TokenUsage,
    ToolCall,
)
from veles.core.tool_args import decode_tool_args

_API_KEY_ENV = "ANTHROPIC_API_KEY"


class AnthropicProvider:
    """Provider backed by Anthropic's native Messages API."""

    name: str = "anthropic"
    supports_tools: bool = True
    supports_streaming: bool = True

    def __init__(
        self,
        *,
        api_key: str | None = None,
        timeout: float = 120.0,
        client: Anthropic | None = None,
    ) -> None:
        if client is not None:
            self._client = client
            return
        from veles.core.provider_factory import require_api_key

        key = require_api_key("anthropic", explicit=api_key)
        self._client = Anthropic(api_key=key, timeout=timeout)

    def create_message(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        *,
        model: str,
        max_tokens: int = 4096,
    ) -> ProviderResponse:
        system, native_messages = _split_system_and_messages(messages)
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": native_messages,
        }
        if system is not None:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = _convert_tools(tools)
        response = self._client.messages.create(**kwargs)
        return _convert_response(response)

    def stream_message(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        *,
        model: str,
        max_tokens: int = 4096,
    ) -> Iterator[StreamEvent]:
        system, native_messages = _split_system_and_messages(messages)
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": native_messages,
            "stream": True,
        }
        if system is not None:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = _convert_tools(tools)

        text_buffer = ""
        current_tool: dict[str, Any] | None = None
        tool_acc: list[dict[str, Any]] = []
        stop_reason: str | None = None
        prompt_tokens = 0
        completion_tokens = 0
        cache_read_tokens = 0
        cache_creation_tokens = 0

        for event in self._client.messages.create(**kwargs):
            et = getattr(event, "type", None)
            if et == "message_start":
                msg = getattr(event, "message", None)
                mu = getattr(msg, "usage", None) if msg is not None else None
                if mu is not None:
                    prompt_tokens = getattr(mu, "input_tokens", 0) or 0
                    completion_tokens = getattr(mu, "output_tokens", 0) or 0
                    cache_read_tokens = getattr(mu, "cache_read_input_tokens", 0) or 0
                    cache_creation_tokens = getattr(mu, "cache_creation_input_tokens", 0) or 0
            elif et == "content_block_start":
                block = getattr(event, "content_block", None)
                btype = getattr(block, "type", None)
                if btype == "tool_use":
                    current_tool = {
                        "id": getattr(block, "id", "") or "",
                        "name": getattr(block, "name", "") or "",
                        "arguments": "",
                    }
            elif et == "content_block_delta":
                delta = getattr(event, "delta", None)
                dtype = getattr(delta, "type", None)
                if dtype == "text_delta":
                    text = getattr(delta, "text", "") or ""
                    if text:
                        text_buffer += text
                        yield TextDelta(text=text)
                elif dtype == "thinking_delta":
                    # Extended-thinking models stream reasoning here (M133).
                    thinking = getattr(delta, "thinking", "") or ""
                    if thinking:
                        yield ReasoningDelta(text=thinking)
                elif dtype == "input_json_delta" and current_tool is not None:
                    current_tool["arguments"] += getattr(delta, "partial_json", "") or ""
            elif et == "content_block_stop":
                if current_tool is not None:
                    tool_acc.append(current_tool)
                    current_tool = None
            elif et == "message_delta":
                ev_delta = getattr(event, "delta", None)
                sr = getattr(ev_delta, "stop_reason", None) if ev_delta is not None else None
                if sr:
                    stop_reason = sr
                ev_usage = getattr(event, "usage", None)
                if ev_usage is not None:
                    out_tokens = getattr(ev_usage, "output_tokens", None)
                    if out_tokens is not None:
                        completion_tokens = out_tokens or 0

        tool_calls: list[ToolCall] = []
        for tc in tool_acc:
            args = decode_tool_args(tc["arguments"])
            tool_calls.append(ToolCall(id=tc["id"], name=tc["name"], arguments=args))

        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_creation_tokens=cache_creation_tokens,
        )
        yield StreamEnd(
            response=ProviderResponse(
                text=text_buffer or None,
                tool_calls=tool_calls,
                usage=usage,
                finish_reason=stop_reason,
                raw=None,
            )
        )


def _split_system_and_messages(
    messages: list[Message],
) -> tuple[str | list[dict[str, Any]] | None, list[dict[str, Any]]]:
    """Convert Veles messages to Anthropic's wire format.

    Returns `(system_or_None, messages_list)`. `system_or_None` is one of:

    - `None` when no system messages are present (or all empty).
    - A plain `str` when the joined system text has no M35 sentinel
      (no caching needed — Anthropic accepts plain strings here).
    - A `list[dict]` of content blocks with `cache_control` on the
      stable prefix when the sentinel is present (M42b prompt-cache).

    Consecutive tool messages merge into one `user` message with
    multiple `tool_result` blocks (Anthropic requires alternating
    user/assistant).
    """
    system_parts: list[str] = []
    out: list[dict[str, Any]] = []
    pending_tool_results: list[dict[str, Any]] = []

    def flush_pending() -> None:
        if pending_tool_results:
            out.append({"role": "user", "content": list(pending_tool_results)})
            pending_tool_results.clear()

    for m in messages:
        if m.role == "system":
            if m.content:
                system_parts.append(m.content)
            continue
        if m.role == "tool":
            pending_tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": m.tool_call_id or "",
                    "content": m.content or "",
                }
            )
            continue
        flush_pending()
        if m.role == "assistant":
            blocks: list[dict[str, Any]] = []
            if m.content:
                blocks.append({"type": "text", "text": m.content})
            for tc in m.tool_calls:
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    }
                )
            out.append({"role": "assistant", "content": blocks if blocks else (m.content or "")})
        elif m.role == "user":
            out.append({"role": "user", "content": m.content or ""})
        else:
            out.append({"role": m.role, "content": m.content or ""})

    flush_pending()
    raw_system = "\n\n".join(system_parts) if system_parts else None
    system = build_anthropic_system_blocks(raw_system)
    return system, out


def _convert_tools(openai_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Translate OpenAI-shaped tool schemas to Anthropic's flat shape."""
    return convert_openai_tools(openai_tools, parameters_key="input_schema")


def _convert_response(response: Any) -> ProviderResponse:
    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    for block in getattr(response, "content", None) or []:
        btype = getattr(block, "type", None)
        if btype == "text":
            text_parts.append(getattr(block, "text", "") or "")
        elif btype == "tool_use":
            arguments = getattr(block, "input", None) or {}
            if not isinstance(arguments, dict):
                arguments = {"_raw": arguments}
            tool_calls.append(
                ToolCall(
                    id=getattr(block, "id", "") or "",
                    name=getattr(block, "name", "") or "",
                    arguments=arguments,
                )
            )
    text = "\n".join(p for p in text_parts if p) or None
    usage_obj = getattr(response, "usage", None)
    prompt_tokens = getattr(usage_obj, "input_tokens", 0) or 0 if usage_obj else 0
    completion_tokens = getattr(usage_obj, "output_tokens", 0) or 0 if usage_obj else 0
    cache_read_tokens = getattr(usage_obj, "cache_read_input_tokens", 0) or 0 if usage_obj else 0
    cache_creation_tokens = (
        getattr(usage_obj, "cache_creation_input_tokens", 0) or 0 if usage_obj else 0
    )
    return ProviderResponse(
        text=text,
        tool_calls=tool_calls,
        usage=TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_creation_tokens=cache_creation_tokens,
        ),
        finish_reason=getattr(response, "stop_reason", None),
        raw=response,
    )
