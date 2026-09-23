"""Mem0 memory adapter (Tier δ, M55 follow-up).

Mem0 (`mem0.ai`) stores user-scoped memories with vector + metadata
search. The adapter wraps `mem0ai.MemoryClient.search(...)` behind the
Veles `MemoryProvider` Protocol. Same lazy-import + silent-degradation
rules as the Honcho adapter — Veles core never hard-requires `mem0ai`.

Configuration source (`~/.veles/config.toml`):

    [memory.external.mem0]
    api_key  = "..."
    user_id  = "your-user-id"
    agent_id = "veles"     # optional; identifies the calling agent
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from veles.core.log_util import warn_once
from veles.core.memory.router import RecallHit
from veles.core.text import ellipsize

_SUMMARY_CAP = 200


@dataclass(slots=True)
class Mem0MemoryProvider:
    api_key: str
    user_id: str
    agent_id: str | None = None
    name: str = "mem0"

    def recall(self, query: str, *, limit: int) -> list[RecallHit]:
        try:
            from mem0 import MemoryClient  # type: ignore[import-not-found]
        except ImportError:
            warn_once("mem0ai not installed; skipping Mem0 recall")
            return []
        try:
            client = MemoryClient(api_key=self.api_key)
            kwargs: dict[str, Any] = {"query": query, "user_id": self.user_id, "limit": limit}
            if self.agent_id:
                kwargs["agent_id"] = self.agent_id
            response = client.search(**kwargs)
        except Exception as exc:
            warn_once(f"Mem0 recall failed: {type(exc).__name__}: {exc}")
            return []
        return [_to_recall_hit(item) for item in _iter_items(response)]


def _iter_items(response: Any) -> list[dict[str, Any]]:
    """Mem0 historically returned `{results: [...]}` and is moving to a
    plain list. Handle both."""
    if isinstance(response, list):
        return [r for r in response if isinstance(r, dict)]
    if isinstance(response, dict):
        for key in ("results", "memories", "items"):
            v = response.get(key)
            if isinstance(v, list):
                return [r for r in v if isinstance(r, dict)]
    return []


def _to_recall_hit(item: dict[str, Any]) -> RecallHit:
    mem_id = str(item.get("id") or item.get("memory_id") or "mem0:unknown")
    memory = str(item.get("memory") or item.get("text") or "")
    summary = ellipsize(memory, _SUMMARY_CAP)
    score = float(item.get("score", 0.0) or 0.0)
    return RecallHit(
        rel_path=f"mem0:{mem_id}",
        title=f"[mem0] {mem_id}",
        summary=summary or "(no summary)",
        score=score,
    )


__all__ = ["Mem0MemoryProvider"]
