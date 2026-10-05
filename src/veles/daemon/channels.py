"""Channel gateways hosted inside the daemon.

`start_channel_runners` reads the declared channels from config and starts one
in-process gateway per enabled channel; `channel_session_map` and
`chat_session_slot` locate the chat→session map a gateway (and a delivery to
its chats) uses.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

from veles.daemon.state import DaemonState

logger = logging.getLogger(__name__)


def channel_session_map(state: DaemonState, platform: str):
    """Per-(session, platform) chat→session map so two daemon sessions running
    the same platform keep independent conversation contexts. The unnamed
    daemon keeps the `<platform>-sessions.json` key."""
    from veles.core.chat_sessions import SessionMap, channel_session_path

    key = f"{state.session_name}-{platform}" if state.session_name else platform
    return SessionMap.load(channel_session_path(key))


def chat_session_slot(state: DaemonState, target: str):
    """`(session map, key)` of the chat a delivery target names, keyed the way
    its gateway keys it (`chat_key_for_target`); None for a non-chat target."""
    from veles.core.chat_sessions import chat_key_for_target

    found = chat_key_for_target(target)
    if found is None:
        return None
    platform, key = found
    return channel_session_map(state, platform), key


def _build_channel_gateway(platform: str, channel_cfg: dict, *, backend, state: DaemonState):
    """Resolve the platform and its secrets, then build one gateway through
    `spec.build(ctx)`. None (and a warning) when no loaded module provides the
    platform or a required secret is missing — a bad channel is skipped, never
    fatal to daemon startup."""
    from veles.core.channel_setup import resolve_secrets
    from veles.core.platforms import ChannelContext, get_platform

    try:
        spec = get_platform(platform)
    except KeyError:
        logger.warning(
            "channel %r: no installed module provides this platform — skipping", platform
        )
        return None
    secrets, missing = resolve_secrets(spec, platform, channel_cfg, project=state.project)
    if missing:
        logger.warning(
            "[channels.%s] enabled but missing %s (keychain veles:%s:%s or config) — "
            "skipping; set it with `veles channel add %s`",
            platform,
            ", ".join(missing),
            platform,
            state.project.name,
            platform,
        )
        return None
    ctx = ChannelContext(
        name=platform,
        config=channel_cfg,
        secrets=secrets,
        backend=backend,
        session_map=channel_session_map(state, platform),
        project=state.project,
    )
    gateway = spec.build(ctx)
    logger.info("channel %r started", platform)
    return gateway


def start_channel_runners(state: DaemonState) -> None:
    """Read declared channels from config and start in-process gateways.

    Generic over platforms (`platform` contributions) and over several
    channels per daemon. For a named session (`state.session_name`) the source
    is `[daemon.<name>.channels.<type>]`; otherwise `[channels.<type>]`. Each
    enabled channel is resolved via the registry and given its own
    `SessionMap`; the run backend is `InProcessRunBackend`, so no HTTP loopback
    or token is needed. Channels with missing creds (or an unregistered
    platform) are skipped with a warning rather than failing daemon startup.
    """
    from veles.core.platforms import get_platform
    from veles.core.project_config import list_channel_configs, load_project_config
    from veles.daemon.in_process_backend import InProcessRunBackend

    cfg = load_project_config(state.project)
    declared = list_channel_configs(cfg, daemon_session=state.session_name)
    if not declared:
        return
    backend = InProcessRunBackend(state)
    for platform, channel_cfg in declared:
        gateway = _build_channel_gateway(platform, channel_cfg, backend=backend, state=state)
        if gateway is None:
            continue
        state.channel_runners.append(gateway)
        state.active_channels.append(platform)
        state.channel_caps[platform] = get_platform(platform).caps
        # Every gateway delivers (`ChannelGateway.deliver`): the channel becomes
        # reachable as `deliver_to = "<platform>:<chat>"`.
        if state.delivery_router is not None:
            state.delivery_router.register_deliverer(platform, gateway.deliver)
        task = asyncio.create_task(_run_channel_gateway(gateway))
        state.channel_tasks.append(task)


async def _run_channel_gateway(gateway) -> None:
    """Wrap `gateway.start()` so a crash doesn't take down the daemon."""
    try:
        await gateway.start()
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.error("channel gateway crashed: %s: %s", type(exc).__name__, exc)
        with contextlib.suppress(Exception):
            await gateway.stop()
