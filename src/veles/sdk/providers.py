"""LLM provider modules: the catalogue contract and a CLI delegate's base.

A module contributes a provider with
`api.contribute("provider", "<id>", ProviderSpec(label=..., build=...))`; `build`
gets a `ProviderContext` and returns an object with `create_message` (and
`stream_message`/`list_models` when it can). A CLI delegate subclasses
`CLIProvider` and, for Veles' tools over MCP, writes a config around
`veles_mcp_server(project)` inside `delegate_dir(project)`.
"""

from __future__ import annotations

from veles.adapters.cli import CLIProvider, StreamState, format_messages_as_prompt, iter_jsonl
from veles.adapters.cli.mcp_config import veles_mcp_server
from veles.core.delegate_dir import delegate_dir
from veles.core.provider import (
    Message,
    ProviderResponse,
    StreamEnd,
    StreamEvent,
    TextDelta,
    TokenUsage,
    ToolCall,
)
from veles.core.providers import ProviderContext, ProviderSpec

__all__ = [
    "CLIProvider",
    "Message",
    "ProviderContext",
    "ProviderResponse",
    "ProviderSpec",
    "StreamEnd",
    "StreamEvent",
    "StreamState",
    "TextDelta",
    "TokenUsage",
    "ToolCall",
    "delegate_dir",
    "format_messages_as_prompt",
    "iter_jsonl",
    "veles_mcp_server",
]
