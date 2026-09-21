"""External memory provider protocol (Tier δ, M55).

The MemoryRouter (M22) ships with two built-in sources: project wiki +
session-turn FTS. M55 lets modules plug additional sources behind the
same surface — Honcho, Mem0, Supermemory, custom corporate KBs — without
touching router code.

A provider implements one required method:

    recall(query: str, *, limit: int) -> list[RecallHit]

and may implement one optional one (M265):

    ingest(title: str, body: str, *, insight_id: int) -> bool

The router collects from every registered provider after its built-in
sources and merges them into the interleaved output. Provider order is
preserved.

**Latency is bounded since M264**: providers run inside the recall fan-out,
which cancels whatever misses `[memory.recall] deadline_sec`, and they run
concurrently with each other so one slow provider no longer starves its
siblings. A provider that hangs costs the deadline, not the turn.

**`ingest` is optional on purpose.** The three shipped adapters (Honcho, Mem0,
Supermemory) were written as read-only sources, and a recall-only provider
stays perfectly valid — the write path checks for the method rather than
requiring it. Without it, whatever is in the external engine got there by some
route other than Veles, which is the state the project was in until M265.
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


@runtime_checkable
class IngestingMemoryProvider(Protocol):
    """A provider Veles can also write to. Checked with `isinstance` at the
    write site, so adapters opt in simply by having the method."""

    name: str

    def ingest(self, title: str, body: str, *, insight_id: int) -> bool: ...


__all__ = ["IngestingMemoryProvider", "MemoryProvider", "RecallHit"]
