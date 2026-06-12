"""DeliveryTarget + DeliveryRouter (M74) — route outbound messages.

Used by the scheduler (M75) and any tool that wants to send a message to a
channel chat from outside the inbound polling loop.

Target syntax (parsed by `DeliveryTarget.parse`):

    local                          → log-only (stderr / .veles/jobs/...).
    origin                         → reply on the same chat that originated
                                     the request (carried by SessionSource).
    <platform>:<chat_id>           → send to that chat on that platform.
    <platform>:<chat_id>:<thread>  → thread-aware variant (Discord, Slack).

The router uses `PlatformRegistry` to look up the channel; each registered
factory may declare a `deliver(chat_id, text, thread_id=None)` coroutine
that the router awaits. If the registered gateway doesn't expose `deliver`
(e.g. the M52 Telegram gateway, which was inbound-only) the router falls
back to `_telegram_direct_deliver` for built-in platforms, or raises
`DeliveryError` otherwise.

Deliberately not a multi-target broadcast DSL — chained delivery is the
caller's responsibility. We keep mirror separate (`channels/mirror.py`) and
delegate truncation to `DisplayTier`, so this layer stays small instead of
absorbing per-platform truncation, attachment handling, and inline mirror
writes.
"""

from __future__ import annotations

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
    """Dispatch outbound messages to channel platforms via the registry.

    Stateless apart from an optional `local_sink` (callable for `local`
    targets) and an optional `origin_handler` callable invoked for `origin`
    targets. Callers wire those when they have a place to land local output
    (e.g. write to wiki, log to stderr) or know the originating chat.
    """

    def __init__(
        self,
        *,
        local_sink=None,
        origin_handler=None,
        platform_deliverers: dict[str, PlatformDeliverer] | None = None,
    ) -> None:
        self._local_sink = local_sink
        self._origin_handler = origin_handler
        self._deliverers: dict[str, PlatformDeliverer] = dict(platform_deliverers or {})

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
            if self._origin_handler is None:
                raise DeliveryError("delivery 'origin' has no origin_handler wired")
            await self._origin_handler(text)
            return {"kind": "origin", "delivered": True}
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
from collections.abc import Awaitable, Callable  # noqa: E402

PlatformDeliverer = Callable[[str, str, str | None], Awaitable[None]]


__all__ = [
    "DeliveryError",
    "DeliveryRouter",
    "DeliveryTarget",
    "PlatformDeliverer",
]
