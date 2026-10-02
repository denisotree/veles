"""Background jobs, worker agents, and the delegation-depth guard for tools that
spawn sub-agents."""

from __future__ import annotations

from veles.core.jobs_store import submit_oneshot_job
from veles.core.orchestration.delegation import (
    MAX_DELEGATE_DEPTH,
    current_delegate_depth,
    current_subagent_factory,
    enter_delegate,
    exit_delegate,
)
from veles.core.orchestration.workers import spawn

__all__ = [
    "MAX_DELEGATE_DEPTH",
    "current_delegate_depth",
    "current_subagent_factory",
    "enter_delegate",
    "exit_delegate",
    "spawn",
    "submit_oneshot_job",
]
