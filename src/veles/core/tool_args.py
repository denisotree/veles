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


# M240: a truncated argument payload looks exactly like a syntax error, and the
# advice for the two is opposite.
#
# Found on the first live GoalMode run (2026-09-01): the model called
# `write_file` with a long markdown report, `Agent`'s default `max_tokens=4096`
# cut the completion mid-string, `decode_tool_args` wrapped the fragment as
# `{"_raw": …}`, and the tool answered "re-issue the call with a single
# well-formed JSON object". The model complied — and hit the identical limit,
# three times, before giving up and pasting the report into chat instead.
# Neither `cli/repl/runtime.py` nor `cli/_agent_builder.py` passes `max_tokens`,
# so 4096 is the effective ceiling on every interactive path.
#
# The fix is not a bigger default (that is a cost decision, and any ceiling can
# be hit). It is to stop giving advice that cannot work: a payload that parses
# as a *prefix* of valid JSON was cut off, not mistyped, and the way out is to
# split the content across calls.
_TRUNCATION_MIN_CHARS = 200


def looks_truncated(raw: object) -> bool:
    """True when `raw` reads as a cut-off JSON object rather than a malformed one.

    Deliberately conservative: an unterminated string or an unclosed brace/bracket
    after a plausible opening. A short fragment is treated as a syntax error —
    genuine model typos are short, truncation happens on big payloads.
    """
    text = str(raw or "")
    if len(text) < _TRUNCATION_MIN_CHARS or not text.lstrip().startswith(("{", "[")):
        return False
    in_string = False
    escaped = False
    depth = 0
    for ch in text:
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
        elif ch == '"':
            in_string = not in_string
        elif not in_string:
            if ch in "{[":
                depth += 1
            elif ch in "}]":
                depth -= 1
    return in_string or depth > 0


def undecodable_args_error(name: str, raw: object) -> str:
    """The message the model sees when its tool arguments could not be decoded."""
    snippet = str(raw)[:200]
    if looks_truncated(raw):
        return (
            f"<error: the arguments for {name} were cut off before the JSON "
            f"ended — the payload is too large for one call, so re-sending it "
            f"unchanged will fail the same way. Split the content across "
            f"several smaller calls (for a file: write the first part, then "
            f"append the rest). Received {len(str(raw))} characters starting "
            f"with: {snippet!r}>"
        )
    return (
        f"<error: the arguments for {name} were not valid JSON — "
        f"re-issue the call with a single well-formed JSON object. "
        f"Received: {snippet!r}>"
    )
