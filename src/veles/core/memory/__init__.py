"""Project memory: the `memory.db` store and the recall built on it.

`SessionStore` (conversation history plus the insight/rule reads recall needs)
and its result types live in `session_store.py`; the schema and its migrations
in `schema.py`. Other modules of this package cover the storage port
(`store.py`), recall routing (`router.py`), the vector index (`vector.py`) and
the on-disk artefacts (`artefacts.py`).
"""

from __future__ import annotations

from veles.core.memory.session_store import (
    DigestRule,
    InsightHit,
    SessionInfo,
    SessionStore,
    TurnHit,
    hide_insight,
)

__all__ = [
    "DigestRule",
    "InsightHit",
    "SessionInfo",
    "SessionStore",
    "TurnHit",
    "hide_insight",
]
