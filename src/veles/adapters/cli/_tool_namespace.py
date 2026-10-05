"""Rewrite Veles short tool names to MCP-qualified names in prompts.

claude-cli (via --mcp-config) exposes Veles tools as `mcp__veles__<name>`.
System prompts authored in short form must be rewritten so the model finds the
tool by exact name; a provider that wires builtin tools directly (OpenRouter, …)
uses short names and must not be rewritten.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable

MCP_SERVER_NAME = "veles"


def claude_mcp_prefix(name: str) -> str:
    return f"mcp__{MCP_SERVER_NAME}__{name}"


def qualify_prompt(
    prompt: str,
    tool_names: Iterable[str],
    *,
    prefix_fn: Callable[[str], str] = claude_mcp_prefix,
) -> str:
    sorted_names = sorted(set(tool_names), key=len, reverse=True)
    for name in sorted_names:
        prompt = re.sub(rf"\b{re.escape(name)}\b", prefix_fn(name), prompt)
    return prompt
