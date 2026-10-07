"""Channel modules: the platform contract and what a gateway talks to.

A module contributes a messaging platform with
`api.contribute("platform", "<name>", PlatformSpec(build=..., ...))`; the daemon
builds the gateway through `build(ChannelContext)`."""

from __future__ import annotations

from veles.core.chat_sessions import SessionMap
from veles.core.platforms import (
    ChannelCaps,
    ChannelContext,
    ChannelGateway,
    CredField,
    PlatformSpec,
    RunBackend,
    RunBackendError,
)

__all__ = [
    "ChannelCaps",
    "ChannelContext",
    "ChannelGateway",
    "CredField",
    "PlatformSpec",
    "RunBackend",
    "RunBackendError",
    "SessionMap",
]
