"""Log-clipping helper shared by the agent loop and the daemon logger.

`truncate_for_log` lives in `veles.core` so `core.tool_dispatch` can import
it at module top level without reaching up into `veles.daemon` (M194).
`daemon.logging` re-exports it for back-compat; `setup_daemon_logging`
stays in the daemon layer (it needs `daemon.paths`).
"""

from __future__ import annotations

DEFAULT_TRUNCATE_CHARS = 2000


def truncate_for_log(text: object, cap: int = DEFAULT_TRUNCATE_CHARS) -> str:
    """Convert `text` to str and elide if over `cap`. The suffix records
    the original byte count so a reader can spot when an interesting
    payload was trimmed."""
    s = str(text) if text is not None else ""
    if cap <= 0 or len(s) <= cap:
        return s
    return f"{s[:cap]}… (truncated, {len(s)} chars total)"
