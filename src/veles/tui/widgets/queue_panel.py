"""Pending-prompt indicator. Visible only when the queue is non-empty.

The bridge appends to `state.queue` whenever a prompt arrives while
the agent is busy; the App drains FIFO on each `TurnDone`. This widget
mirrors what's currently waiting, so the user can see how many turns
are still in flight before their next composition is consumed.

Up arrow in an empty composer pops the *newest* queued prompt back
into the composer for editing (see `Composer._queue_provider`). That
pop happens through the bridge, which also refreshes this panel.
"""

from __future__ import annotations

from collections import deque

from textual.widgets import Static

_PREVIEW_MAX = 60
_PREVIEW_COUNT = 3


class QueuePanel(Static):
    DEFAULT_CSS = """
    QueuePanel {
        background: $surface;
        color: $text-muted;
        border-top: tall $primary 30%;
        padding: 0 1;
        height: auto;
        max-height: 5;
    }
    """

    def __init__(self) -> None:
        super().__init__("", id="veles-queue-panel")
        self.display = False
        # Plain-text mirror so tests can inspect the rendered content
        # without poking Static internals.
        self.last_text: str = ""

    def render_queue(self, queue: deque[str]) -> None:
        if not queue:
            self.display = False
            self.last_text = ""
            self.update("")
            return
        self.display = True
        rows = [f"queue: {len(queue)} pending (Up arrow on empty composer edits the newest)"]
        # Newest first: deque[-1] is the most recent enqueue.
        recent = list(queue)[-_PREVIEW_COUNT:][::-1]
        for item in recent:
            preview = item.replace("\n", " ")
            if len(preview) > _PREVIEW_MAX:
                preview = preview[: _PREVIEW_MAX - 1] + "…"
            rows.append(f"  ▸ {preview}")
        text = "\n".join(rows)
        self.last_text = text
        self.update(text)
