from __future__ import annotations

import os
import subprocess

from veles.core.context import current_project
from veles.core.critical_ops import AGENT_SHELL_ENV
from veles.core.path_guard import sandbox_cwd
from veles.core.risk import RiskClass
from veles.core.sandbox import notes, wrap
from veles.core.tools.registry import tool

_MAX_OUTPUT_BYTES = 8 * 1024


@tool(
    risk_class=RiskClass.PROCESS_EXECUTION,
    side_effects=["filesystem", "process"],
)
def run_shell(command: str, timeout: int = 30) -> str:
    """Run `command` via `bash -c` and return combined stdout+stderr.

    Output is truncated to 8 KiB. Exit code is appended on the final line.
    The command runs in the active project root (M37: falling back to cwd) and,
    where one is available, in an OS sandbox (`core/sandbox.py`): git hooks/config,
    auto-run files, agent-CLI configs and Veles state are read-only. The M38 trust
    ladder and M39 always-confirm still gate the call itself.
    """
    project = current_project()
    wrapped = wrap(["bash", "-c", command], project)
    try:
        result = subprocess.run(
            wrapped.argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            cwd=str(sandbox_cwd()),
            stdin=subprocess.DEVNULL,  # never the user's terminal: no prompt reads their keys
            env={**os.environ, AGENT_SHELL_ENV: "1"},  # `veles … approve` refuses it
        )
    except subprocess.TimeoutExpired:
        return f"<timeout after {timeout}s>"
    body = (result.stdout or "") + (result.stderr or "")
    extra = notes(wrapped, returncode=result.returncode, output=body, project=project)
    if len(body) > _MAX_OUTPUT_BYTES:
        body = body[:_MAX_OUTPUT_BYTES] + f"\n<truncated to {_MAX_OUTPUT_BYTES} bytes>"
    return f"{body}\n<exit {result.returncode}>" + (f"\n{extra}" if extra else "")
