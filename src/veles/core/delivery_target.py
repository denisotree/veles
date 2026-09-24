"""Where an outbound message goes: the `deliver_to` grammar.

    local                          → log-only (stderr / .veles/jobs/...).
    origin                         → the chat that originated the request;
                                     callers resolve it to a platform target
                                     before delivery.
    <platform>:<chat_id>           → send to that chat on that platform.
    <platform>:<chat_id>:<thread>  → thread-aware variant (Discord, Slack).

Lives in core because jobs and task tools validate targets; the router that
actually delivers is `channels.delivery.DeliveryRouter`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(slots=True, frozen=True)
class DeliveryTarget:
    """Parsed `local` | `origin` | `<platform>:<chat_id>[:<thread_id>]`."""

    kind: Literal["local", "origin", "platform"]
    platform: str | None = None
    chat_id: str | None = None
    thread_id: str | None = None

    @classmethod
    def parse(cls, spec: str) -> DeliveryTarget:
        s = (spec or "").strip()
        if not s:
            raise ValueError("delivery target is empty")
        if s == "local":
            return cls(kind="local")
        if s == "origin":
            return cls(kind="origin")
        parts = s.split(":", 2)
        if len(parts) < 2 or not parts[0] or not parts[1]:
            raise ValueError(
                f"unrecognised delivery target {spec!r}; "
                "expected 'local' | 'origin' | '<platform>:<chat_id>[:<thread>]'"
            )
        platform, chat_id = parts[0], parts[1]
        thread_id = parts[2] if len(parts) == 3 and parts[2] else None
        return cls(kind="platform", platform=platform, chat_id=chat_id, thread_id=thread_id)

    def render(self) -> str:
        """Inverse of parse — round-trip representation."""
        if self.kind == "local":
            return "local"
        if self.kind == "origin":
            return "origin"
        base = f"{self.platform}:{self.chat_id}"
        if self.thread_id:
            return f"{base}:{self.thread_id}"
        return base


__all__ = ["DeliveryTarget"]
