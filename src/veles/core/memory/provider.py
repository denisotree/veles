"""External memory provider protocol (Tier δ, M55).

The MemoryRouter (M22) ships with two built-in sources: project wiki +
session-turn FTS. M55 lets modules plug additional sources behind the
same surface — Honcho, Mem0, Supermemory, custom corporate KBs — without
touching router code.

A provider implements one method:

    recall(query: str, *, limit: int) -> list[RecallHit]

The router collects from every registered provider after its built-in
sources and merges them into the interleaved output. Provider order is
preserved; latency is the provider's problem (a slow provider blocks the
turn — wrap in your own timeout / cache if needed).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from veles.core.memory.router import RecallHit


@runtime_checkable
class MemoryProvider(Protocol):
    """One queryable memory source. Implementations are usually thin
    adapters around external APIs (Honcho, Mem0, ...) or local stores."""

    name: str

    def recall(self, query: str, *, limit: int) -> list[RecallHit]: ...


__all__ = ["MemoryProvider", "RecallHit"]
