"""Composer integration — multiline edit, submit, tab cycle, history,
$EDITOR launch (mocked).

We host the Composer inside a tiny test app rather than the full
`TuiApp` so the focus stays on key bindings, not slash routing.
"""

from __future__ import annotations

from textual.app import App, ComposeResult

from veles.cli.repl.completer import SlashCompleter
from veles.cli.repl.history import InputHistory
from veles.cli.repl.slash import SlashRegistry, SlashResult
from veles.tui.widgets.composer import Composer


def _make_registry(*names: str) -> SlashRegistry:
    reg = SlashRegistry()
    for n in names:
        reg.register(n, lambda r, c: SlashResult.ok(), summary="")
    return reg


class _ComposerHost(App):
    """Captures `Composer.Submitted` so tests can assert what was sent."""

    def __init__(self, *, history: InputHistory, completer: SlashCompleter | None = None) -> None:
        super().__init__()
        self._history = history
        self._completer = completer
        self.submitted: list[str] = []

    def compose(self) -> ComposeResult:
        self.composer = Composer(history=self._history, completer=self._completer)
        yield self.composer

    def on_composer_submitted(self, event: Composer.Submitted) -> None:
        self.submitted.append(event.value)


# ---------------- enter / shift+enter ----------------


async def test_enter_submits_and_clears(tmp_path):
    app = _ComposerHost(history=InputHistory.load(tmp_path / "h.jsonl"))
    async with app.run_test() as pilot:
        app.composer.text = "hello"
        await pilot.press("enter")
        await pilot.pause()
        assert app.submitted == ["hello"]
        assert app.composer.text == ""


async def test_empty_enter_is_a_noop(tmp_path):
    app = _ComposerHost(history=InputHistory.load(tmp_path / "h.jsonl"))
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
        assert app.submitted == []


async def test_shift_enter_inserts_newline(tmp_path):
    app = _ComposerHost(history=InputHistory.load(tmp_path / "h.jsonl"))
    async with app.run_test() as pilot:
        app.composer.focus()
        app.composer.text = "line1"
        # Move cursor to end so the newline lands after the existing text.
        from textual.widgets import TextArea

        TextArea.action_cursor_line_end(app.composer)
        await pilot.press("shift+enter")
        await pilot.pause()
        assert app.composer.text == "line1\n"
        assert app.submitted == []  # nothing submitted yet


# ---------------- history ----------------


async def test_submit_appends_to_history_and_persists(tmp_path):
    path = tmp_path / "h.jsonl"
    app = _ComposerHost(history=InputHistory.load(path))
    async with app.run_test() as pilot:
        for entry in ("alpha", "beta"):
            app.composer.text = entry
            await pilot.press("enter")
            await pilot.pause()
    reloaded = InputHistory.load(path)
    assert reloaded.items == ["alpha", "beta"]


async def test_up_arrow_navigates_history(tmp_path):
    history = InputHistory.load(tmp_path / "h.jsonl")
    history.append("alpha")
    history.append("beta")
    app = _ComposerHost(history=history)
    async with app.run_test() as pilot:
        app.composer.focus()
        await pilot.press("up")
        await pilot.pause()
        assert app.composer.text == "beta"
        await pilot.press("up")
        await pilot.pause()
        assert app.composer.text == "alpha"


async def test_down_arrow_restores_draft_past_newest(tmp_path):
    history = InputHistory.load(tmp_path / "h.jsonl")
    history.append("alpha")
    app = _ComposerHost(history=history)
    async with app.run_test() as pilot:
        app.composer.focus()
        app.composer.text = "draft"
        await pilot.press("up")  # → "alpha"
        await pilot.pause()
        assert app.composer.text == "alpha"
        await pilot.press("down")  # past newest → restore draft
        await pilot.pause()
        assert app.composer.text == "draft"


async def test_escape_cancels_history_navigation(tmp_path):
    history = InputHistory.load(tmp_path / "h.jsonl")
    history.append("entry")
    app = _ComposerHost(history=history)
    async with app.run_test() as pilot:
        app.composer.focus()
        app.composer.text = "in-progress"
        await pilot.press("up")
        await pilot.pause()
        assert app.composer.text == "entry"
        await pilot.press("escape")
        await pilot.pause()
        assert app.composer.text == "in-progress"


# ---------------- tab cycle ----------------


async def test_tab_cycles_through_matches(tmp_path):
    completer = SlashCompleter(_make_registry("/save", "/search", "/session"))
    app = _ComposerHost(history=InputHistory.load(tmp_path / "h.jsonl"), completer=completer)
    async with app.run_test() as pilot:
        app.composer.focus()
        app.composer.text = "/s"
        # Move cursor past the typed text so the completer sees prefix "/s".
        from textual.widgets import TextArea

        TextArea.action_cursor_line_end(app.composer)
        await pilot.press("tab")
        await pilot.pause()
        assert app.composer.text == "/save"
        await pilot.press("tab")
        await pilot.pause()
        assert app.composer.text == "/search"
        await pilot.press("tab")
        await pilot.pause()
        assert app.composer.text == "/session"
        await pilot.press("tab")
        await pilot.pause()
        # Wrap to first.
        assert app.composer.text == "/save"


async def test_tab_with_no_matches_is_noop(tmp_path):
    completer = SlashCompleter(_make_registry("/help"))
    app = _ComposerHost(history=InputHistory.load(tmp_path / "h.jsonl"), completer=completer)
    async with app.run_test() as pilot:
        app.composer.focus()
        app.composer.text = "/xyz"
        from textual.widgets import TextArea

        TextArea.action_cursor_line_end(app.composer)
        await pilot.press("tab")
        await pilot.pause()
        assert app.composer.text == "/xyz"


# ---------------- $EDITOR ----------------


async def test_ctrl_g_launches_editor_and_loads_result(tmp_path, monkeypatch):
    """We patch the subprocess runner so no real editor spawns. The
    runner appends a line to the tmp file the composer wrote."""
    from veles.tui.widgets import composer as composer_mod

    called: list[list[str]] = []

    def fake_runner(cmd: list[str]) -> int:
        called.append(cmd)
        # cmd[-1] is the tmp path the Composer wrote.
        from pathlib import Path as _PathT

        path = _PathT(cmd[-1])
        path.write_text(path.read_text(encoding="utf-8") + " [edited]", encoding="utf-8")
        return 0

    monkeypatch.setattr(composer_mod, "_default_subprocess_runner", fake_runner)
    monkeypatch.setattr(composer_mod, "_stdin_is_tty", lambda: True)
    # Force the tmp dir under the test's tmp_path so we don't touch ~/.tmp/.
    monkeypatch.setattr(composer_mod, "_veles_tmp_dir", lambda: tmp_path)
    # `app.suspend()` requires a properly attached terminal in real
    # operation; under Pilot it's a no-op context. Patch it to a stub
    # so the call doesn't choke on Pilot's fake driver.
    from contextlib import contextmanager

    @contextmanager
    def fake_suspend(self):
        yield

    from textual.app import App as _App

    monkeypatch.setattr(_App, "suspend", fake_suspend)

    app = _ComposerHost(history=InputHistory.load(tmp_path / "h.jsonl"))
    async with app.run_test() as pilot:
        app.composer.focus()
        app.composer.text = "draft"
        await pilot.press("ctrl+g")
        await pilot.pause()
        assert called and called[0][-1].endswith(".md")
        assert app.composer.text == "draft [edited]"


async def test_ctrl_g_failure_keeps_original_text(tmp_path, monkeypatch):
    from contextlib import contextmanager

    from textual.app import App as _App

    from veles.tui.widgets import composer as composer_mod

    monkeypatch.setattr(composer_mod, "_default_subprocess_runner", lambda cmd: 1)
    monkeypatch.setattr(composer_mod, "_stdin_is_tty", lambda: True)
    monkeypatch.setattr(composer_mod, "_veles_tmp_dir", lambda: tmp_path)

    @contextmanager
    def fake_suspend(self):
        yield

    monkeypatch.setattr(_App, "suspend", fake_suspend)

    app = _ComposerHost(history=InputHistory.load(tmp_path / "h.jsonl"))
    async with app.run_test() as pilot:
        app.composer.focus()
        app.composer.text = "untouched"
        await pilot.press("ctrl+g")
        await pilot.pause()
        assert app.composer.text == "untouched"
