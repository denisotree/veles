from __future__ import annotations

import subprocess

from veles.core.path_guard import sandbox_cwd
from veles.core.risk import RiskClass
from veles.core.tools.registry import tool

_MAX_OUTPUT_BYTES = 8 * 1024


@tool(
    risk_class=RiskClass.PROCESS_EXECUTION,
    side_effects=["filesystem", "process"],
)
def run_shell(command: str, timeout: int = 30) -> str:
    """Run `command` via `bash -c` and return combined stdout+stderr.

    Output is truncated to 8 KiB. Exit code is appended on the final line.
    The command runs with the user's full privileges and best-effort sandbox
    cwd (M37: active project root, falling back to cwd). Real shell sandboxing
    is impossible without OS-level guardrails — M38 trust-ladder + M39
    always-confirm provide the user-facing guard.
    """
    try:
        result = subprocess.run(
            ["bash", "-c", command],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            cwd=str(sandbox_cwd()),
        )
    except subprocess.TimeoutExpired:
        return f"<timeout after {timeout}s>"
    body = (result.stdout or "") + (result.stderr or "")
    if len(body) > _MAX_OUTPUT_BYTES:
        body = body[:_MAX_OUTPUT_BYTES] + f"\n<truncated to {_MAX_OUTPUT_BYTES} bytes>"
    return f"{body}\n<exit {result.returncode}>"
