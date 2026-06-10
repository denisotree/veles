"""Rewrite Veles short tool names to MCP-qualified names in prompts.

claude-cli (via --mcp-config) and gemini-cli (via .gemini/settings.json
with --allowed-mcp-server-names) expose Veles tools under different
naming conventions:
  - claude:  `mcp__veles__<name>` (double underscore, anthropic convention)
  - gemini:  `mcp_veles_<name>`   (single underscore, gemini-cli 0.40.x)

System prompts authored in short form must be rewritten so the model finds
the tool by exact name. OpenRouter wires builtin tools directly with short
names — for that provider this rewrite is a no-op and must not be applied.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable

MCP_SERVER_NAME = "veles"


def claude_mcp_prefix(name: str) -> str:
    return f"mcp__{MCP_SERVER_NAME}__{name}"


def gemini_mcp_prefix(name: str) -> str:
    return f"mcp_{MCP_SERVER_NAME}_{name}"


# Backward-compatible alias: pre-M17 callers used `mcp_prefix` for claude.
mcp_prefix = claude_mcp_prefix


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
