"""Sanitization of untrusted MCP tool schemas (M157).

MCP servers are third-party processes: tool names, descriptions and
JSON-Schema fragments they return are untrusted input that gets spliced
into the agent's prompt. A hostile or merely odd server could otherwise
inject instructions ("ignore previous rules...") or blow up the prompt
with megabyte schemas. Caps:

  - tool names must match ``^[A-Za-z0-9_-]{1,64}$`` after normalization
    (control chars / surrounding whitespace stripped) — rejected otherwise;
  - max 16 parameters per tool (extras dropped);
  - max 64 chars per parameter name (longer ones dropped);
  - max 400 chars per description / hint (truncated with an ellipsis);
  - control characters and newlines stripped from names and descriptions;
  - non-dict schemas replaced by an empty object schema.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

MAX_PARAMS_PER_TOOL = 16
MAX_PARAM_NAME_CHARS = 64
MAX_TEXT_CHARS = 400

TOOL_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]+")
_WHITESPACE_RE = re.compile(r"\s+")

_EMPTY_OBJECT_SCHEMA: dict[str, Any] = {"type": "object", "properties": {}}

# JSON-Schema keys preserved per property. Anything else (examples, $refs,
# nested combinators) is dropped — the model only needs name/type/description.
_KEPT_PROPERTY_KEYS = ("type", "description", "enum", "default", "items")


def sanitize_text(value: Any, limit: int = MAX_TEXT_CHARS) -> str:
    """Make an untrusted string safe for prompt splicing.

    Control chars and newlines become single spaces, whitespace collapses,
    and the result is capped at `limit` chars with a trailing ellipsis."""
    text = _CONTROL_CHARS_RE.sub(" ", str(value))
    text = _WHITESPACE_RE.sub(" ", text).strip()
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def normalize_tool_name(name: Any) -> str | None:
    """Normalize an MCP tool name; None when it can't be made safe.

    Normalization strips control characters and surrounding whitespace
    only — we deliberately do NOT rewrite arbitrary junk into a valid
    name, because a silently renamed tool would no longer match the
    server's own tool id at call time."""
    text = _CONTROL_CHARS_RE.sub("", str(name)).strip()
    if not TOOL_NAME_RE.match(text):
        logger.warning("MCP tool name %r is not a safe identifier; rejecting tool", name)
        return None
    return text


def _sanitize_property(value: Any) -> dict[str, Any]:
    """Keep only the prompt-relevant keys of one property schema."""
    if not isinstance(value, dict):
        return {}
    out: dict[str, Any] = {}
    for key in _KEPT_PROPERTY_KEYS:
        if key not in value:
            continue
        item = value[key]
        if key == "description":
            out[key] = sanitize_text(item)
        elif key == "type":
            if isinstance(item, str):
                out[key] = sanitize_text(item, limit=MAX_PARAM_NAME_CHARS)
            elif isinstance(item, list):
                out[key] = [
                    sanitize_text(t, limit=MAX_PARAM_NAME_CHARS) for t in item if isinstance(t, str)
                ]
        elif key == "enum":
            if isinstance(item, list):
                out[key] = [
                    sanitize_text(v, limit=MAX_PARAM_NAME_CHARS) if isinstance(v, str) else v
                    for v in item[:MAX_PARAMS_PER_TOOL]
                ]
        elif key == "items":
            out[key] = _sanitize_property(item)
        else:  # default
            out[key] = sanitize_text(item) if isinstance(item, str) else item
    return out


def sanitize_schema(schema: Any) -> dict[str, Any]:
    """Sanitize an untrusted MCP `inputSchema` into a bounded object schema.

    Non-dict input yields the empty object schema. Parameter count is
    capped at `MAX_PARAMS_PER_TOOL` (insertion order wins), parameter
    names with control chars or > `MAX_PARAM_NAME_CHARS` are dropped,
    `required` is filtered down to surviving parameters."""
    if not isinstance(schema, dict):
        return dict(_EMPTY_OBJECT_SCHEMA, properties={})

    properties: dict[str, Any] = {}
    raw_props = schema.get("properties")
    if isinstance(raw_props, dict):
        for pname, pvalue in raw_props.items():
            if len(properties) >= MAX_PARAMS_PER_TOOL:
                logger.warning(
                    "MCP schema: more than %d parameters; extras dropped",
                    MAX_PARAMS_PER_TOOL,
                )
                break
            name_text = str(pname)
            if _CONTROL_CHARS_RE.search(name_text) or _WHITESPACE_RE.search(name_text):
                logger.warning("MCP schema: dropping parameter with unsafe name %r", pname)
                continue
            if not name_text or len(name_text) > MAX_PARAM_NAME_CHARS:
                logger.warning("MCP schema: dropping parameter with oversized name %r", pname)
                continue
            properties[name_text] = _sanitize_property(pvalue)

    out: dict[str, Any] = {"type": "object", "properties": properties}
    raw_required = schema.get("required")
    if isinstance(raw_required, list):
        required = [r for r in raw_required if isinstance(r, str) and r in properties]
        if required:
            out["required"] = required
    return out


__all__ = [
    "MAX_PARAMS_PER_TOOL",
    "MAX_PARAM_NAME_CHARS",
    "MAX_TEXT_CHARS",
    "TOOL_NAME_RE",
    "normalize_tool_name",
    "sanitize_schema",
    "sanitize_text",
]
