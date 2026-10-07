"""Project memory for modules: recall hits, memory providers, memory artefacts."""

from __future__ import annotations

from veles.core.dreaming import DreamResult
from veles.core.fts import escape_query
from veles.core.memory.artefacts import append_memory_log, write_proposal
from veles.core.memory.inspectors import recent_insights, recent_rules
from veles.core.memory.provider import IngestingMemoryProvider, MemoryProvider
from veles.core.memory.router import RecallHit
from veles.core.memory.store import open_store

__all__ = [
    "DreamResult",
    "IngestingMemoryProvider",
    "MemoryProvider",
    "RecallHit",
    "append_memory_log",
    "escape_query",
    "open_store",
    "recent_insights",
    "recent_rules",
    "write_proposal",
]
