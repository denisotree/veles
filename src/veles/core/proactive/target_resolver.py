"""Resolve where a proactive notice is delivered (M214).

Proactivity is a daemon-only affair (only the daemon has the long-running loops
and live channels). When the dream loop wants to notify the user of a dated
event there is no originating message to reply to, so the target is resolved
dynamically:

1. `[proactive] target` in the project config, if pinned — a deterministic
   override for operators who want a fixed chat.
2. otherwise the **last active channel**: across every started channel's
   `SessionMap`, the chat with the most recent `last_used_at`. Its map key
   (`telegram:<chat_id>`) is already a `DeliveryRouter` target string.

Returns `None` on a cold start (no channel has ever seen a message). The caller
(`ReminderRunner`) treats `None` as "not resolvable yet" and retries next tick
— never dropping the notice. `last_active_target` is the pure, testable core;
`resolve_last_active_target` is the thin `DaemonState` adapter.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

# NOTE: `veles.channels` is imported lazily inside the functions, not at module
# top level — `veles.core` must not statically import an upper layer (M194
# import-isolation invariant). This resolver is core-resident because the
# ReminderRunner (core) needs it, but it reads channel session maps.


def _config_target(project: Any) -> str | None:
    """The pinned `[proactive] target`, or None. Best-effort: a malformed
    config must never break delivery."""
    try:
        from veles.core.project_config import get_section, load_project_config

        val = get_section(load_project_config(project), "proactive").get("target")
    except Exception:
        return None
    text = str(val).strip() if val else ""
    return text or None


def last_active_target(channels: Iterable[str], *, base_dir: Path | None = None) -> str | None:
    """The `<platform>:<chat_id>` of the most-recently-active chat across the
    given channels' session maps, or None when none have any entries."""
    from veles.channels.session_map import SessionMap, channel_session_path

    best_key: str | None = None
    best_ts = float("-inf")
    for channel in channels:
        path = channel_session_path(channel, base_dir=base_dir)
        for key, _sid, last_used in SessionMap.load(path).list():
            if last_used > best_ts:
                best_ts, best_key = last_used, key
    return best_key


def resolve_last_active_target(state: Any) -> str | None:
    """Config override first, else the last active channel across
    `state.active_channels`. None means "not resolvable yet" (cold start)."""
    override = _config_target(state.project)
    if override:
        return override
    return last_active_target(state.active_channels)


__all__ = ["last_active_target", "resolve_last_active_target"]
