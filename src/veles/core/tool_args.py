"""JSON-decode LLM tool-call arguments with a `{"_raw": ...}` fallback.

Every wire adapter accumulates tool-call arguments as a JSON string and
must turn it into the dict `ToolCall.arguments` expects. The failure
contract is shared (M151): malformed JSON never raises — the raw string
is preserved under `{"_raw": <raw>}` so the agent loop can surface it to
the model instead of crashing the turn. Lives in `core/` (not
`adapters/`) because `core/openai_wire.py` needs it too and core must
never import from adapters.
"""

from __future__ import annotations

import json
from typing import Any


def decode_tool_args(raw: Any) -> dict[str, Any]:
    """Decode a tool-call arguments payload into a dict.

    - dict input passes through unchanged (some providers hand decoded
      args directly).
    - `None`/empty string decodes to `{}`.
    - A JSON string decodes via `json.loads`; on `JSONDecodeError` the
      original value is wrapped as `{"_raw": raw}`.
    """
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {"_raw": raw}
