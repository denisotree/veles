"""DeliveryTarget + DeliveryRouter (M74) — route outbound messages.

Used by the scheduler (M75) and any tool that wants to send a message to a
channel chat from outside the inbound polling loop.

Target syntax (parsed by `DeliveryTarget.parse`):

    local                          → log-only (stderr / .veles/jobs/...).
    origin                         → the chat that originated the request;
                                     callers resolve it to a platform target
                                     before delivery (the router refuses it).
    <platform>:<chat_id>           → send to that chat on that platform.
    <platform>:<chat_id>:<thread>  → thread-aware variant (Discord, Slack).

Each running channel registers a deliverer for its platform
(`channels.start_channel_runners`); a platform target with no deliverer
raises `DeliveryError`.

Deliberately not a multi-target broadcast DSL — chained delivery is the
caller's responsibility. Recording a delivery in the receiving chat's session
is the caller's too: the runners pass an `on_delivered` hook (M214's binder,
`daemon/background_ops.make_proactive_binder`; M273 for jobs).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from veles.channels.platform_registry import get_platform


class DeliveryError(RuntimeError):
    """Raised by DeliveryRouter when a target cannot be reached."""


@dataclass(slots=True, frozen=True)
class DeliveryTarget:
    """Parsed `local` | `origin` | `<platform>:<chat_id>[:<thread_id>]`."""

    kind: str  # 'local' | 'origin' | 'platform'
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


class DeliveryRouter:
    """Dispatch outbound messages to the deliverers channels register, plus an
    optional `local_sink` for `local` targets (e.g. log to stderr)."""

    def __init__(self, *, local_sink: Callable[[str], None] | None = None) -> None:
        self._local_sink = local_sink
        self._deliverers: dict[str, PlatformDeliverer] = {}

    def register_deliverer(self, platform: str, deliverer: PlatformDeliverer) -> None:
        """Attach a deliverer for a given platform (overrides the registry path)."""
        self._deliverers[platform] = deliverer

    async def deliver(self, target: DeliveryTarget | str, text: str) -> dict[str, object]:
        """Send `text` to `target`. Returns a small dict describing what happened."""
        tgt = target if isinstance(target, DeliveryTarget) else DeliveryTarget.parse(target)
        if tgt.kind == "local":
            if self._local_sink is None:
                return {"kind": "local", "delivered": False, "reason": "no local_sink wired"}
            self._local_sink(text)
            return {"kind": "local", "delivered": True}
        if tgt.kind == "origin":
            raise DeliveryError("resolve 'origin' to the originating chat before delivering")
        # platform
        assert tgt.platform is not None and tgt.chat_id is not None
        deliverer = self._deliverers.get(tgt.platform)
        if deliverer is None:
            # No explicit deliverer wired — look up via the platform registry.
            try:
                get_platform(tgt.platform)
            except KeyError as exc:
                raise DeliveryError(str(exc)) from exc
            raise DeliveryError(
                f"platform {tgt.platform!r} is registered but no deliverer is wired; "
                "call DeliveryRouter.register_deliverer() before delivering"
            )
        await deliverer(tgt.chat_id, text, tgt.thread_id)
        return {"kind": "platform", "platform": tgt.platform, "delivered": True}


# Signature for platform-specific outbound senders.
PlatformDeliverer = Callable[[str, str, str | None], Awaitable[None]]


__all__ = [
    "DeliveryError",
    "DeliveryRouter",
    "DeliveryTarget",
    "PlatformDeliverer",
]
