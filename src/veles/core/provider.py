"""Provider protocol — what every LLM-backend adapter must satisfy.

Why this lives in core: every other component (agent loop, future memory recall,
future curator) talks to LLMs through this single surface. Adapters implement
it; core never imports from adapters.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Protocol


class ProviderError(Exception):
    """Base for adapter-surfaced failures the agent should treat as a
    failed turn (not a crash). Adapters may raise subclasses; the agent
    records them as `ErrorEvent`s (M132)."""


class ProviderTimeout(ProviderError):
    """The provider call exceeded its read/connect timeout. Adapters
    translate their SDK's native timeout into this typed exception so the
    agent and UI can label it distinctly instead of guessing from a
    backend-specific class name (M132)."""


class ProviderUnavailable(ProviderError):
    """The provider's server could not be reached at all — connection
    refused, DNS failure, or network down. The common local-model case:
    `ollama`/`llamacpp` isn't running and veles knocked on a closed port.
    Adapters translate the SDK's connection error into this typed
    exception with an actionable hint instead of a silent hang (M132b)."""


@dataclass(slots=True)
class ToolCall:
    """A function call requested by the model. `arguments` is already JSON-decoded."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class Message:
    """One turn in a conversation. Provider-agnostic."""

    role: str  # "system" | "user" | "assistant" | "tool"
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None  # only set when role == "tool"


@dataclass(slots=True)
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    # M250: the slice of `completion_tokens` the model spent thinking, when the
    # upstream reports it (`completion_tokens_details.reasoning_tokens`). A
    # reasoning model's visible answer is the tail of its completion budget, so
    # "empty answer" and "budget exhausted by thinking" are only separable with
    # this number. 0 means "not reported", not "no thinking".
    reasoning_tokens: int = 0
    # M250: real cost of this call as billed upstream, when reported
    # (OpenRouter's `usage.cost`). 0.0 means "not reported" — the trace's
    # `est_cost_usd` was a hardcoded 0.0 before this.
    cost_usd: float = 0.0


@dataclass(slots=True)
class ProviderResponse:
    """One LLM completion. Either `text` is set, or `tool_calls` is non-empty, or both."""

    text: str | None
    tool_calls: list[ToolCall]
    usage: TokenUsage
    finish_reason: str | None = None
    raw: Any = None  # provider-native object kept for debugging
    # M250: the backend that actually served this call, as reported by a relay
    # that fans out across providers (OpenRouter puts `provider` on the
    # completion AND on every stream chunk). Recorded in the trace so a
    # measurement run can state which backend answered instead of assuming the
    # pin held — including the case where a mistyped pin silently did nothing.
    # None for direct providers, which are their own backend.
    upstream_provider: str | None = None


@dataclass(slots=True)
class TextDelta:
    """Incremental chunk of assistant text emitted during streaming."""

    text: str


@dataclass(slots=True)
class ReasoningDelta:
    """Incremental chunk of the model's *reasoning* (a.k.a. thinking) stream,
    distinct from the user-facing answer text (M133).

    Reasoning-capable models expose their chain-of-thought separately:
    Anthropic via `thinking_delta` content blocks, OpenAI/OpenRouter via a
    `reasoning` / `reasoning_content` field on the streamed delta. Adapters
    emit this so the agent can surface reasoning in the inspector without
    polluting the answer shown in chat. Providers that don't expose
    reasoning simply never yield it (graceful — the UI keeps "thinking…")."""

    text: str


@dataclass(slots=True)
class StreamEnd:
    """Terminal event of a streaming session — carries the assembled response."""

    response: ProviderResponse


StreamEvent = TextDelta | ReasoningDelta | StreamEnd


class Provider(Protocol):
    """Minimal provider surface."""

    name: str
    supports_streaming: bool

    # Read-only in the protocol: the subscription-CLI adapters compute it.
    @property
    def supports_tools(self) -> bool: ...

    def create_message(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        *,
        model: str,
        max_tokens: int = 4096,
    ) -> ProviderResponse: ...

    def stream_message(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        *,
        model: str,
        max_tokens: int = 4096,
    ) -> Iterator[StreamEvent]: ...
