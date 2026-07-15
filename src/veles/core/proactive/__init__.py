"""Proactive delivery (M214) — the daemon notifying the user of definite dated
events without a triggering message.

Pieces:
- `target_resolver` — where an unsolicited notice goes when there is no active
  session/origin: the last active channel (or a config-pinned target).

Discovery (dream extracts definite events) materialises into the `tasks` table
as `source='dream'` reminders; the `ReminderRunner` delivers them. This package
holds only the daemon-side glue that the reminder sweep and dream loop reuse.
"""

from __future__ import annotations

from veles.core.proactive.target_resolver import (
    last_active_target,
    resolve_last_active_target,
)

__all__ = ["last_active_target", "resolve_last_active_target"]
