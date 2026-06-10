"""Pick a session to resume from the store.

Pulls the most recent N sessions through `SessionStore.list_sessions`
and presents them with id + last-activity timestamp + turn count +
title. The picker's haystack concatenates all four so the filter input
can target any of them.
"""

from __future__ import annotations

import datetime as dt

from veles.core.memory import SessionStore
from veles.tui.screens.base_picker import PickerItem, PickerScreen


def _fmt_ts(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts, tz=dt.UTC).strftime("%Y-%m-%d %H:%M")


class SessionPickerScreen(PickerScreen[str]):
    """Returns the picked `session_id`. `None` on cancel."""

    def __init__(self, store: SessionStore, *, limit: int = 50, current: str | None = None) -> None:
        self._store = store
        self._current = current
        items = self._build_items(limit)
        super().__init__(
            title="Pick a session (Esc to cancel)",
            items=items,
            empty_message="no sessions yet",
            placeholder="filter by id / title / date…",
        )

    def _build_items(self, limit: int) -> list[PickerItem[str]]:
        items: list[PickerItem[str]] = []
        for info in self._store.list_sessions(limit=limit):
            title = info.title or "(untitled)"
            marker = "* " if info.id == self._current else "  "
            ts = _fmt_ts(info.last_activity_at)
            label = f"{marker}{info.id}  {ts}  turns={info.turn_count}  {title}"
            haystack = f"{info.id} {ts} {title}"
            items.append(PickerItem(label=label, haystack=haystack, value=info.id))
        return items
