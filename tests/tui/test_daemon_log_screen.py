"""M110: DaemonLogScreen — tail a daemon's log file inside the TUI."""

from __future__ import annotations

from pathlib import Path

from textual.app import App

from veles.tui.screens.daemon_log import DaemonLogScreen


class _Host(App):
    """Pushes the screen on mount so we can drive it via Pilot."""

    def __init__(self, screen: DaemonLogScreen) -> None:
        super().__init__()
        self._screen = screen
        self.popped = False

    def on_mount(self) -> None:
        self.push_screen(self._screen)


async def test_log_view_renders_existing_content(tmp_path: Path) -> None:
    log_path = tmp_path / "daemon-alpha.log"
    log_path.write_text("first line\nsecond line\n", encoding="utf-8")
    screen = DaemonLogScreen(log_path, slug="alpha")
    app = _Host(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        # _offset advanced past the file body.
        assert screen._offset == log_path.stat().st_size
        await pilot.press("q")
        await pilot.pause()


async def test_log_view_q_pops_back(tmp_path: Path) -> None:
    log_path = tmp_path / "daemon-alpha.log"
    log_path.write_text("hi\n", encoding="utf-8")
    screen = DaemonLogScreen(log_path, slug="alpha")
    app = _Host(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        # After q, the host App pops back; there's no underlying screen
        # so Textual exits the app.
        await pilot.press("q")
        await pilot.pause()


async def test_log_view_handles_missing_file(tmp_path: Path) -> None:
    log_path = tmp_path / "daemon-nope.log"
    screen = DaemonLogScreen(log_path, slug="nope")
    app = _Host(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Sentinel set so we don't repeat the empty marker.
        assert screen._offset == 1
        await pilot.press("q")
        await pilot.pause()


async def test_log_view_tails_appended_lines(tmp_path: Path) -> None:
    log_path = tmp_path / "daemon-alpha.log"
    log_path.write_text("first\n", encoding="utf-8")
    screen = DaemonLogScreen(log_path, slug="alpha")
    app = _Host(screen)
    async with app.run_test() as pilot:
        await pilot.pause()
        first_offset = screen._offset
        # Append more content; manual refresh picks it up.
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write("second\nthird\n")
        screen._tail()
        await pilot.pause()
        assert screen._offset > first_offset
        await pilot.press("q")
        await pilot.pause()
