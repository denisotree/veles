"""M110: live tail of a daemon's log file.

Pushed by `DaemonPickerScreen` when the user presses Enter on a row.
Reads `~/.veles/logs/daemon-<slug>.log` from offset 0, then tails it on
a 1-second interval. Reading is non-blocking (small chunks via Path
.read_text); the file rotates when it crosses 5 MiB so we never accumulate
unbounded text in the RichLog.

Bindings:
  q / Esc — pop back to the picker
  F5      — manual refresh (rare; auto-tail handles the common case)
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, RichLog


class DaemonLogScreen(Screen[None]):
    """Read-only view onto a single daemon log file.

    The picker stays underneath in the screen stack so popping returns
    the user to the same row they had selected.
    """

    DEFAULT_CSS = """
    DaemonLogScreen { background: $surface; }
    DaemonLogScreen Vertical { padding: 1 2; }
    DaemonLogScreen Label.title {
        color: $accent;
        text-style: bold;
        margin-bottom: 1;
    }
    DaemonLogScreen Label.hint {
        color: $text-muted;
        margin-top: 1;
    }
    DaemonLogScreen RichLog {
        height: 1fr;
        background: $surface;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("q", "back", "back", priority=True),
        Binding("escape", "back", "back", priority=True),
        Binding("f5", "refresh", "refresh", priority=True),
    ]

    def __init__(self, log_path: Path, *, slug: str) -> None:
        super().__init__()
        self._log_path = log_path
        self._slug = slug
        self._offset = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            yield Label(
                f"daemon log · {self._slug} · {self._log_path}",
                classes="title",
            )
            self._log = RichLog(highlight=True, markup=False, wrap=True, max_lines=2000)
            yield self._log
            yield Label("q/Esc=back · F5=refresh", classes="hint")
        yield Footer()

    def on_mount(self) -> None:
        # Read whatever already exists, then poll for additions every
        # second. 1s feels live without thrashing the FS on tiny logs.
        self._tail()
        self.set_interval(1.0, self._tail)

    def _tail(self) -> None:
        try:
            size = self._log_path.stat().st_size
        except OSError:
            # File missing — render a one-shot empty marker and stop.
            if self._offset == 0:
                self._log.write(f"<no log file at {self._log_path} yet>")
                self._offset = 1  # don't repeat
            return
        if size < self._offset:
            # Log rotated under us; start fresh from offset 0.
            self._log.write("<log rotated — resuming from start>")
            self._offset = 0
        if size == self._offset:
            return
        try:
            with self._log_path.open("r", encoding="utf-8", errors="replace") as fh:
                fh.seek(self._offset)
                chunk = fh.read()
                self._offset = fh.tell()
        except OSError as exc:
            self._log.write(f"<read error: {exc}>")
            return
        if not chunk:
            return
        for line in chunk.splitlines():
            self._log.write(line)

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_refresh(self) -> None:
        self._tail()


__all__ = ["DaemonLogScreen"]
