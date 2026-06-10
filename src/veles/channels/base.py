"""Channel protocol — every gateway implements this shape.

A channel translates between an external chat surface (Telegram, Slack,
…) and the M51 daemon. The base layer is intentionally tiny — every
concrete gateway provides `start()` / `stop()` and handles its own
transport.

`ChannelMessage` is the normalised one-way envelope from the external
surface into the agent loop: a user identity tuple plus their text. The
gateway is free to add channel-specific metadata as it sees fit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True, frozen=True)
class ChannelMessage:
    """One inbound message from an external chat surface.

    `chat_id` is the external identity used as the session-map key
    (Telegram chat_id, Slack channel id, etc.). `user_id` is the
    sender (often equal to chat_id in direct-message channels). `text`
    is the raw user content forwarded to the agent.
    """

    channel: str
    chat_id: str
    user_id: str
    text: str


class ChannelGateway(Protocol):
    """Long-running gateway between an external chat surface and the daemon."""

    name: str

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
