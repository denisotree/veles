"""Queue UI + composer pop-back hook.

Covers:
  - `QueuePanel` is hidden when the queue is empty, visible otherwise,
    and renders the newest entries first.
  - `Composer.queue_provider`, when set, takes priority over history
    navigation while the composer is empty.
  - `AgentBridge.pop_last_for_edit` returns the deque's right end.
  - Full App: two queued prompts → Up arrow pops the newest into the
    composer; queue panel updates to reflect one pending entry.
"""

from __future__ import annotations

from collections import deque

from textual.app import App, ComposeResult

from veles.core.session_state import AppState
from veles.tui.app import TuiApp
from veles.tui.bridge import AgentBridge
from veles.tui.history import InputHistory
from veles.tui.widgets.composer import Composer
from veles.tui.widgets.queue_panel import QueuePanel

# ---------------- QueuePanel ----------------


class _QueueHost(App):
    def __init__(self) -> None:
        super().__init__()
        self.panel = QueuePanel()

    def compose(self) -> ComposeResult:
        yield self.panel


async def test_queue_panel_hidden_when_empty():
    async with _QueueHost().run_test() as pilot:
        pilot.app.panel.render_queue(deque())
        assert not pilot.app.panel.display
        assert pilot.app.panel.last_text == ""


async def test_queue_panel_renders_newest_first():
    async with _QueueHost().run_test() as pilot:
        pilot.app.panel.render_queue(deque(["a", "b", "c"]))
        assert pilot.app.panel.display
        text = pilot.app.panel.last_text
        # Newest (c) shown above older entries (b, a).
        assert text.index("▸ c") < text.index("▸ b") < text.index("▸ a")
        assert "3 pending" in text


async def test_queue_panel_truncates_long_previews():
    long = "x" * 200
    async with _QueueHost().run_test() as pilot:
        pilot.app.panel.render_queue(deque([long]))
        # Truncated with ellipsis; the original 200-char line is gone.
        assert "…" in pilot.app.panel.last_text
        assert long not in pilot.app.panel.last_text


# ---------------- composer queue_provider ----------------


class _ComposerHost(App):
    def __init__(self, queue: deque[str]) -> None:
        super().__init__()
        self._queue = queue

    def compose(self) -> ComposeResult:
        # Lazy InputHistory under a path that won't be touched (Composer
        # never calls `append` when the test only exercises Up arrow).
        self.composer = Composer(history=InputHistory(path=__import__("pathlib").Path("/dev/null")))
        self.composer.queue_provider = self._pop
        yield self.composer

    def _pop(self) -> str | None:
        if not self._queue:
            return None
        return self._queue.pop()


async def test_up_pops_from_queue_when_composer_empty():
    queue = deque(["first", "second"])
    app = _ComposerHost(queue)
    async with app.run_test() as pilot:
        app.composer.focus()
        await pilot.press("up")
        await pilot.pause()
        assert app.composer.text == "second"
        assert list(queue) == ["first"]
        # Another Up pops the remaining entry.
        app.composer.text = ""
        await pilot.press("up")
        await pilot.pause()
        assert app.composer.text == "first"
        assert list(queue) == []


async def test_up_falls_through_to_history_when_queue_empty():
    """Empty queue → composer.action_history_up runs its normal path
    (no exception, no spurious text change)."""
    queue = deque()
    app = _ComposerHost(queue)
    async with app.run_test() as pilot:
        app.composer.focus()
        await pilot.press("up")
        await pilot.pause()
        # No history entries either → text stays empty.
        assert app.composer.text == ""


# ---------------- AgentBridge.pop_last_for_edit ----------------


def test_pop_last_for_edit_returns_newest_then_none():
    state = AppState(session_id=None, provider_name="x", model="m")
    state.queue.extend(("a", "b", "c"))
    bridge = AgentBridge(app=None, state=state, factory=lambda s: None)  # type: ignore[arg-type]
    assert bridge.pop_last_for_edit() == "c"
    assert bridge.pop_last_for_edit() == "b"
    assert bridge.pop_last_for_edit() == "a"
    assert bridge.pop_last_for_edit() is None


# ---------------- TuiApp integration ----------------


async def test_app_up_arrow_pops_queue_and_refreshes_panel(
    tmp_project, agent_factory_for, text_response
):
    """Two prompts queued; pressing Up in the empty composer pops the
    most recent back for editing and shrinks the queue."""
    project, store = tmp_project
    state = AppState(session_id=None, provider_name="stub", model="m")
    # Pre-seed the queue rather than racing the worker thread — much
    # more reliable than enqueueing during a live turn.
    state.queue.extend(("first", "second"))
    app = TuiApp(
        state=state,
        agent_factory=agent_factory_for(text_response("ok")),
        project=project,
        store=store,
    )
    async with app.run_test() as pilot:
        panel = pilot.app.query_one(QueuePanel)
        # `on_mount` renders the seeded queue.
        assert "2 pending" in panel.last_text
        composer = pilot.app.query_one(Composer)
        composer.focus()
        await pilot.press("up")
        await pilot.pause()
        assert composer.text == "second"
        assert list(pilot.app.state.queue) == ["first"]
        assert "1 pending" in panel.last_text
