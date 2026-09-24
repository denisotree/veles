"""DeliveryRouter (M74) — route outbound messages.

Used by the scheduler (M75) and any tool that wants to send a message to a
channel chat from outside the inbound polling loop. Targets use the
`core.delivery_target.DeliveryTarget` grammar; the router refuses an
unresolved `origin`.

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

from veles.channels.platform_registry import get_platform
from veles.core.delivery_target import DeliveryTarget


class DeliveryError(RuntimeError):
    """Raised by DeliveryRouter when a target cannot be reached."""


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
    "PlatformDeliverer",
]
