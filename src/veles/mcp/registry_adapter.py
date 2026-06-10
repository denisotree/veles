"""MCP tools → Veles tool Registry (M157).

`register_mcp_tools` turns each connected server's discovered tools into
ordinary `ToolEntry` objects named ``mcp_<server>_<tool>``, so the
Permission Engine, trust ladder and planning-mode rules see them exactly
like builtin tools.

Risk-class mapping (annotations are server-provided and untrusted, so we
only ever *relax* to read-only on an explicit ``readOnlyHint: true``,
and harden on anything else):

  - ``destructiveHint: true``      → ``RiskClass.DESTRUCTIVE``
                                     (always_confirm — never bypassable).
  - ``readOnlyHint: true``         → ``RiskClass.READ_ONLY`` (allow).
  - anything else / no annotations → ``RiskClass.NETWORK_OPEN_WORLD``
                                     (sensitive → approval via trust ladder).
"""

from __future__ import annotations

import logging
from typing import Any

from veles.core.risk import RiskClass, is_sensitive_class
from veles.core.tools.registry import Registry, ToolEntry
from veles.mcp.client import McpClientManager
from veles.mcp.config import McpServerConfig
from veles.mcp.sanitize import normalize_tool_name, sanitize_schema, sanitize_text

logger = logging.getLogger(__name__)

_NON_TEXT_PLACEHOLDER = "[non-text content: {kind}]"


def _annotation(tool: Any, key: str) -> Any:
    """Read one annotation hint from an SDK Tool object or a plain dict."""
    ann = getattr(tool, "annotations", None)
    if ann is None and isinstance(tool, dict):
        ann = tool.get("annotations")
    if ann is None:
        return None
    if isinstance(ann, dict):
        return ann.get(key)
    return getattr(ann, key, None)


def classify_risk(tool: Any) -> RiskClass:
    """Map MCP annotation hints to a Veles risk class. See module docstring."""
    if _annotation(tool, "destructiveHint") is True:
        return RiskClass.DESTRUCTIVE
    if _annotation(tool, "readOnlyHint") is True:
        return RiskClass.READ_ONLY
    return RiskClass.NETWORK_OPEN_WORLD


def result_to_text(result: Any) -> str:
    """Flatten an SDK CallToolResult into plain text for the model.

    Text blocks are concatenated; non-text blocks (images, resources)
    become short placeholders. An ``isError`` result is prefixed so the
    model sees the failure as such."""
    blocks = getattr(result, "content", None)
    if blocks is None and isinstance(result, dict):
        blocks = result.get("content")
    parts: list[str] = []
    for block in blocks or []:
        text = getattr(block, "text", None)
        if text is None and isinstance(block, dict):
            text = block.get("text")
        if isinstance(text, str):
            parts.append(text)
            continue
        kind = getattr(block, "type", None)
        if kind is None and isinstance(block, dict):
            kind = block.get("type")
        parts.append(_NON_TEXT_PLACEHOLDER.format(kind=kind or "unknown"))
    text_out = "\n".join(parts) if parts else "(empty MCP result)"
    is_error = getattr(result, "isError", None)
    if is_error is None and isinstance(result, dict):
        is_error = result.get("isError")
    if is_error:
        return f"MCP tool error: {text_out}"
    return text_out


def _make_handler(
    manager: McpClientManager, server: str, tool_name: str, timeout_s: float
):
    def handler(**arguments: Any) -> str:
        try:
            result = manager.call_tool(
                server, tool_name, dict(arguments), timeout_s=timeout_s
            )
        except Exception as exc:
            return f"MCP call failed ({server}/{tool_name}): {exc}"
        return result_to_text(result)

    return handler


def register_mcp_tools(
    registry: Registry,
    manager: McpClientManager,
    configs: dict[str, McpServerConfig],
    *,
    disabled_tools: dict[str, list[str]] | None = None,
) -> list[str]:
    """Register every connected server's tools into `registry`.

    Skips disabled tools, tools whose names fail sanitization, and name
    collisions (warned, never raised). Returns the registered names."""
    disabled = disabled_tools or {}
    statuses = manager.status()
    registered: list[str] = []
    for server in sorted(configs):
        cfg = configs[server]
        if not cfg.enabled:
            continue
        status = statuses.get(server)
        if status is None or status.state != "connected":
            continue
        skip = set(disabled.get(server, ()))
        for tool in manager.list_tools(server):
            raw_name = getattr(tool, "name", None)
            if raw_name is None and isinstance(tool, dict):
                raw_name = tool.get("name")
            safe_name = normalize_tool_name(raw_name) if raw_name is not None else None
            if safe_name is None:
                continue
            if safe_name in skip or (raw_name in skip):
                logger.info("MCP tool %s/%s disabled by config; skipping", server, safe_name)
                continue
            entry_name = f"mcp_{server}_{safe_name}"
            raw_description = getattr(tool, "description", None)
            if raw_description is None and isinstance(tool, dict):
                raw_description = tool.get("description")
            description = sanitize_text(raw_description or f"MCP tool {safe_name} on {server}")
            raw_schema = getattr(tool, "inputSchema", None)
            if raw_schema is None and isinstance(tool, dict):
                raw_schema = tool.get("inputSchema")
            risk = classify_risk(tool)
            entry = ToolEntry(
                name=entry_name,
                description=f"[MCP:{server}] {description}",
                parameter_schema=sanitize_schema(raw_schema),
                handler=_make_handler(manager, server, safe_name, cfg.timeout_s),
                is_async=False,
                sensitive=is_sensitive_class(risk),
                risk_class=risk,
                side_effects=["network", f"mcp:{server}"],
                timeout_s=cfg.timeout_s,
            )
            try:
                registry.register(entry)
            except ValueError as exc:
                logger.warning("skipping MCP tool %r: %s", entry_name, exc)
                continue
            registered.append(entry_name)
    return registered


__all__ = ["classify_risk", "register_mcp_tools", "result_to_text"]
