"""Shared wire-format helpers for native (non-OpenAI-relay) adapters.

The agent core hands every adapter tool specs in OpenAI's
`{"type": "function", "function": {name, description, parameters}}` shape.
The Anthropic and Gemini adapters both flatten that into a native dict;
the *only* difference between them is the key the JSON schema lands under
(`input_schema` for Anthropic, `parameters` for Gemini). Centralised here
(M151) so both share one set of edge cases: flat (function-less) entries,
non-dict entries skipped, missing name/description defaulting to "", and
a null/empty schema normalised to `{type: "object", properties: {}}`.
"""

from __future__ import annotations

from typing import Any


def convert_openai_tools(
    tools: list[dict[str, Any]], *, parameters_key: str
) -> list[dict[str, Any]]:
    """Translate OpenAI-shaped tool schemas to a flat native shape.

    `parameters_key` names the field the JSON schema is stored under
    in the output (`"input_schema"` for Anthropic, `"parameters"` for
    Gemini function_declarations).
    """
    out: list[dict[str, Any]] = []
    for t in tools:
        fn = t.get("function") if isinstance(t.get("function"), dict) else t
        if not isinstance(fn, dict):
            continue
        out.append(
            {
                "name": fn.get("name", ""),
                "description": fn.get("description", ""),
                parameters_key: fn.get("parameters") or {"type": "object", "properties": {}},
            }
        )
    return out
