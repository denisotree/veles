"""Honcho memory adapter (Tier δ, M55 follow-up).

Honcho (`honcho.dev`) stores per-user, per-app conversation memories
and exposes a search API. The adapter wraps that surface as a Veles
`MemoryProvider`. SDK is imported lazily — Veles core has no hard
dependency on `honcho-ai`. Users install it explicitly when they want
this provider plugged into their `MemoryRouter`.

Failure modes that downgrade silently to `[]` (logged to stderr in
verbose mode):
  - `honcho_ai` not installed
  - HTTP error / connection refused
  - empty / malformed response shape
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any

from veles.core.memory.router import RecallHit

_SUMMARY_CAP = 200


@dataclass(slots=True)
class HonchoMemoryProvider:
    """Pulls memories from a Honcho session for the configured user.

    `api_key`   — Honcho API token; usually loaded from
                  `~/.veles/config.toml [memory.external.honcho].api_key`.
    `app_id`    — Honcho app identifier (one per Veles project is typical).
    `user_id`   — user inside that app whose memories we want.
    `base_url`  — optional override for self-hosted Honcho.
    """

    api_key: str
    app_id: str
    user_id: str
    base_url: str | None = None
    name: str = "honcho"

    def recall(self, query: str, *, limit: int) -> list[RecallHit]:
        try:
            from honcho_ai import Honcho  # type: ignore[import-not-found]
        except ImportError:
            _warn_once("honcho-ai not installed; skipping Honcho recall")
            return []
        try:
            client = (
                Honcho(api_key=self.api_key, base_url=self.base_url)
                if self.base_url
                else Honcho(api_key=self.api_key)
            )
            response = client.search(
                app_id=self.app_id,
                user_id=self.user_id,
                query=query,
                limit=limit,
            )
        except Exception as exc:
            _warn_once(f"Honcho recall failed: {type(exc).__name__}: {exc}")
            return []
        return [_to_recall_hit(item) for item in _iter_items(response)]


def _iter_items(response: Any) -> list[dict[str, Any]]:
    """Honcho's SDK returns either a list, a paginated object, or a dict
    with `items` — handle all three so a minor SDK bump doesn't break us."""
    if isinstance(response, list):
        return [r for r in response if isinstance(r, dict)]
    items = getattr(response, "items", None) or getattr(response, "results", None)
    if isinstance(items, list):
        return [r for r in items if isinstance(r, dict)]
    if isinstance(response, dict):
        return [r for r in response.get("items", []) if isinstance(r, dict)]
    return []


def _to_recall_hit(item: dict[str, Any]) -> RecallHit:
    rel_path = str(item.get("id") or item.get("ref") or "honcho:unknown")
    title = str(item.get("title") or item.get("name") or rel_path)
    content = str(item.get("content") or item.get("text") or item.get("summary") or "")
    summary = content.strip().replace("\n", " ")
    if len(summary) > _SUMMARY_CAP:
        summary = summary[: _SUMMARY_CAP - 1].rstrip() + "…"
    score = float(item.get("score", 0.0) or 0.0)
    return RecallHit(
        rel_path=f"honcho:{rel_path}",
        title=f"[honcho] {title}",
        summary=summary or "(no summary)",
        score=score,
    )


_warned: set[str] = set()


def _warn_once(msg: str) -> None:
    if msg in _warned:
        return
    _warned.add(msg)
    print(f"warning: {msg}", file=sys.stderr)


__all__ = ["HonchoMemoryProvider"]
