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
    from veles.channels.session_map import SessionMap, channel_session_path

    key = f"{state.session_name}-{platform}" if state.session_name else platform
    return SessionMap.load(channel_session_path(key))


def chat_session_slot(state: DaemonState, target: str):
    """`(session map, key)` of the chat a delivery target names, keyed the way
    its gateway keys it (`chat_key_for_target`); None for a non-chat target."""
    from veles.channels.session_map import chat_key_for_target

    found = chat_key_for_target(target)
    if found is None:
        return None
    platform, key = found
    return channel_session_map(state, platform), key


def _float_setting(cfg: dict, key: str) -> float | None:
    """Read an optional numeric channel setting. A typo warns and falls
    back to the code default rather than crashing daemon startup."""
    raw = cfg.get(key)
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        logger.warning("[channels.telegram] %s=%r is not a number — using the default", key, raw)
        return None


def _build_channel_gateway(platform: str, channel_cfg: dict, *, backend, state: DaemonState):
    """Resolve creds + build one gateway via the platform registry. Returns
    None (and warns) when the platform is unregistered or its token is
    missing — a bad channel is skipped, never fatal to daemon startup."""
    from veles.channels.platform_registry import get_platform
    from veles.core.secrets import get_provider_key

    try:
        entry = get_platform(platform)
    except KeyError:
        logger.warning("channel %r is not a registered platform — skipping", platform)
        return None
    token = get_provider_key(platform, project=state.project.name) or channel_cfg.get("bot_token")
    if not token:
        logger.warning(
            "[channels.%s] enabled but no bot token in keychain (veles:%s:%s) or config — skipping",
            platform,
            platform,
            state.project.name,
        )
        return None
    session_map = channel_session_map(state, platform)
    if platform == "telegram":
        raw_whitelist = channel_cfg.get("whitelist") or []
        if isinstance(raw_whitelist, str):
            raw_whitelist = [raw_whitelist]
        whitelist = tuple(str(x) for x in raw_whitelist if str(x).strip())
        # Stdin-fallback wizard wrote chat_id as a single allowed peer; honor it.
        legacy_chat_id = channel_cfg.get("chat_id")
        if legacy_chat_id and not whitelist:
            whitelist = (str(legacy_chat_id),)
        gateway = entry.factory(
            bot_token=str(token),
            daemon_client=backend,
            session_map=session_map,
            whitelist=whitelist,
            attachment_dir=state.project.tmp_dir,
            project_root=state.project.root,
            debounce_seconds=_float_setting(channel_cfg, "debounce_seconds"),
            forward_debounce_seconds=_float_setting(channel_cfg, "forward_debounce_seconds"),
        )
        logger.info("telegram channel started (whitelist: %d entries)", len(whitelist))
        return gateway
    # Generic platforms use the minimal factory contract shared with
    # `veles channel run` (bot_token / daemon_client / session_map).
    gateway = entry.factory(bot_token=str(token), daemon_client=backend, session_map=session_map)
    logger.info("channel %r started", platform)
    return gateway


def start_channel_runners(state: DaemonState) -> None:
    """Read declared channels from config and start in-process gateways.

    Generic over platforms (`channels/platform_registry`) and over several
    channels per daemon. For a named session (`state.session_name`) the source
    is `[daemon.<name>.channels.<type>]`; otherwise `[channels.<type>]`. Each
    enabled channel is resolved via the registry and given its own
    `SessionMap`; the run backend is `InProcessRunBackend`, so no HTTP loopback
    or token is needed. Channels with missing creds (or an unregistered
    platform) are skipped with a warning rather than failing daemon startup.
    """
    from veles.channels.platform_registry import ensure_builtins_registered
    from veles.core.project_config import list_channel_configs, load_project_config
    from veles.daemon.in_process_backend import InProcessRunBackend

    ensure_builtins_registered()
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
        # Expose this channel as an outbound delivery target for the scheduler:
        # a gateway implementing `deliver(chat_id, text, thread_id)` becomes
        # reachable via `deliver_to = "<platform>:<chat>"`.
        if state.delivery_router is not None:
            deliver_fn = getattr(gateway, "deliver", None)
            if callable(deliver_fn):
                state.delivery_router.register_deliverer(platform, deliver_fn)
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
