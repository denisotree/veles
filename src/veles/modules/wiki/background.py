"""The wiki engine's `background_op` contribution: the `kind="ingest"` daemon job
(moved from `daemon/background_ops.py`). Drives the batch ingest kernel directly
with ingest-scoped sub-agents — no LLM job-agent at all (audit M5 determinism +
M2 untrusted-content isolation)."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from veles.sdk import Project

from .ingest import (
    INGEST_AGENT_SYSTEM_PROMPT,
    IngestOutcome,
    batch_ingest_files,
    ingest_user_message,
    run_batch_ingest,
)

# Per-project serialization of wiki-mutating ops (audit: cross-JOB dedup).
# `JobRunner` runs up to `max_parallel` jobs — two concurrent recursive
# ingests would race each other's `wiki_search` and mint duplicate topic
# pages. The kernel's own loop already serializes WITHIN one job.
_INGEST_LOCKS: dict[str, threading.Lock] = {}
_INGEST_LOCKS_GUARD = threading.Lock()


def _project_ingest_lock(project: Project) -> threading.Lock:
    key = str(project.root)
    with _INGEST_LOCKS_GUARD:
        return _INGEST_LOCKS.setdefault(key, threading.Lock())


def run_ingest_job(job: Any, *, spawn_agent: Callable[[str], Any], project: Project) -> str:
    params = job.params or {}
    source = str(params.get("source") or "")
    pattern = str(params.get("glob") or "*")
    root = Path(source)
    if not root.is_dir():
        raise ValueError(f"ingest source is not a directory: {source!r}")
    files = batch_ingest_files(root, pattern)
    if not files:
        return f"No files under {source!r} match {pattern!r}; nothing ingested."

    def spawn_one(path: Path) -> IngestOutcome:
        agent = spawn_agent(INGEST_AGENT_SYSTEM_PROMPT)
        result = agent.run(ingest_user_message(str(path)))
        ok = getattr(result, "stopped_reason", "completed") == "completed"
        return IngestOutcome(
            source=str(path),
            ok=ok,
            detail="" if ok else f"stopped: {getattr(result, 'stopped_reason', '?')}",
        )

    with _project_ingest_lock(project):
        result = run_batch_ingest(files, spawn_one=spawn_one)
    return result.summary()
