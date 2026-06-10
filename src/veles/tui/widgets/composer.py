"""Multiline composer (Phase 4).

Built on Textual's `TextArea` so multi-line drafts work natively. The
Phase-1 single-line `Input` shape is replaced wholesale — the App
listens for `Composer.Submitted` now, not `Input.Submitted`. The two
events carry the same payload (`value: str`).

Key map:
    Enter            → submit  (priority binding overrides TextArea's newline)
    Shift+Enter      → insert newline
    Ctrl+G           → suspend Textual, open $EDITOR on the current draft,
                       reload its contents
    Tab              → cycle through completer candidates
    Up / Down        → history navigation when the draft has no newlines,
                       otherwise cursor movement (default TextArea behaviour)
    Escape           → cancel an active history walk and restore the
                       draft that was on screen before nav started

Cycle semantics: each fresh Tab press recomputes candidates if the
buffer changed since the last press; otherwise it advances the index
within the cached list. After cycling past the last candidate, we wrap
back to the first.
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import ClassVar

from textual.binding import Binding
from textual.message import Message
from textual.widgets import TextArea

from veles.tui.completer import Completer, NullCompleter
from veles.tui.history import InputHistory

# Returns the text of the most-recent queued prompt to re-edit, or
# `None` if the queue is empty. Hooked from `TuiApp.on_mount`.
QueuePopProvider = Callable[[], str | None]


class Composer(TextArea):
    DEFAULT_CSS = """
    Composer {
        background: $surface;
        border-top: tall $primary;
        padding: 0 1;
        height: auto;
        max-height: 10;
        min-height: 3;
    }
    """

    # Priority bindings overrule TextArea's built-in Enter→newline action.
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("enter", "submit_text", "submit", priority=True, show=False),
        Binding("shift+enter", "newline_char", "newline", priority=True, show=False),
        Binding("ctrl+j", "newline_char", "newline", priority=True, show=False),
        Binding("ctrl+g", "launch_editor", "edit in $EDITOR"),
        Binding("up", "history_up", "history prev", show=False),
        Binding("down", "history_down", "history next", show=False),
        Binding("tab", "complete", "complete", show=False),
        Binding("escape", "cancel_history", "cancel history", show=False),
        # Cross-platform word/line editing aliases on top of TextArea's
        # built-in actions. Ctrl+W / Ctrl+F / Ctrl+U / Ctrl+K / Ctrl+Left/Right
        # and Ctrl+Shift+Left/Right are already inherited from TextArea.
        # macOS Alt-convention (Option as Meta):
        Binding("alt+backspace", "delete_word_left", show=False),
        Binding("alt+delete", "delete_word_right", show=False),
        Binding("alt+left", "cursor_word_left", show=False),
        Binding("alt+right", "cursor_word_right", show=False),
        Binding("alt+shift+left", "cursor_word_left(True)", show=False),
        Binding("alt+shift+right", "cursor_word_right(True)", show=False),
        # Linux / Windows Ctrl-convention (VS Code / Sublime / Windows Terminal):
        Binding("ctrl+backspace", "delete_word_left", show=False),
        Binding("ctrl+delete", "delete_word_right", show=False),
        # macOS Cmd-convention (works in terminals that pass Super through —
        # kitty, WezTerm, iTerm with CSI-u). Harmless elsewhere.
        Binding("super+backspace", "delete_to_start_of_line", show=False),
        Binding("super+delete", "delete_to_end_of_line_or_delete_line", show=False),
        Binding("super+left", "cursor_line_start", show=False),
        Binding("super+right", "cursor_line_end", show=False),
        Binding("super+shift+left", "cursor_line_start(True)", show=False),
        Binding("super+shift+right", "cursor_line_end(True)", show=False),
        Binding("super+z", "undo", show=False),
        Binding("super+shift+z", "redo", show=False),
    ]

    class Submitted(Message):
        """Emitted on Enter with non-empty text. Carries the literal draft."""

        def __init__(self, value: str) -> None:
            super().__init__()
            self.value = value

    def __init__(
        self,
        *,
        history: InputHistory | None = None,
        completer: Completer | None = None,
        queue_provider: QueuePopProvider | None = None,
        project_root_provider: Callable[[], Path | None] | None = None,
    ) -> None:
        super().__init__(id="veles-composer", show_line_numbers=False, soft_wrap=True)
        self.input_history = history or InputHistory.load()
        self.completer = completer or NullCompleter()
        # `queue_provider`, when set, is consulted by `action_history_up`
        # whenever the composer is empty: a non-`None` return value pops
        # the newest queued prompt back for editing. When `None` (or the
        # composer holds text), history navigation runs as usual.
        self.queue_provider: QueuePopProvider | None = queue_provider
        # M78: callable returning the project root used by the `@` file
        # picker. Set by TuiApp on mount; None disables the picker.
        self.project_root_provider: Callable[[], Path | None] | None = (
            project_root_provider
        )
        # Tab-cycle state: candidates plus the buffer that produced them.
        # Re-tabbing only advances the index while the buffer is unchanged;
        # any edit resets the cycle in `on_text_area_changed`.
        self._tab_cycle: list[str] = []
        self._tab_index: int = -1
        self._tab_origin: str | None = None

    # ---- Composer-owned actions ----

    def action_submit_text(self) -> None:
        value = self.text
        self._reset_tab_cycle()
        self.input_history.reset()
        self.text = ""
        if value.strip():
            self.input_history.append(value)
            self.post_message(self.Submitted(value))

    def action_newline_char(self) -> None:
        self.insert("\n")
        self._reset_tab_cycle()

    def action_history_up(self) -> None:
        """Up routing (in priority order):
          - multiline draft & not navigating → cursor up
          - empty draft & queue non-empty   → pop the newest queued
            prompt back into the composer (no history step taken)
          - otherwise                       → previous history entry
        """
        if "\n" in self.text and not self.input_history.navigating:
            TextArea.action_cursor_up(self)
            return
        if (
            not self.text
            and self.queue_provider is not None
            and not self.input_history.navigating
        ):
            popped = self.queue_provider()
            if popped is not None:
                self._replace_text(popped)
                return
        if not self.input_history.navigating:
            self.input_history.start_navigation(self.text)
        prev = self.input_history.previous()
        if prev is not None:
            self._replace_text(prev)

    def action_history_down(self) -> None:
        if "\n" in self.text and not self.input_history.navigating:
            TextArea.action_cursor_down(self)
            return
        nxt = self.input_history.next()
        if nxt is not None:
            self._replace_text(nxt)

    def action_cancel_history(self) -> None:
        if self.input_history.navigating:
            draft = self.input_history._draft
            self.input_history.reset()
            self._replace_text(draft)

    def on_text_area_changed(self, event) -> None:
        """M78: watch for `@` typed at a word boundary (whitespace or
        start of text immediately before the cursor) and open the inline
        FilePickerScreen. TextArea consumes printable keys before any
        binding can fire, so we detect via the post-insertion text watch."""
        del event
        if not self.text:
            return
        cursor = self._compute_cursor_offset()
        # The just-typed char sits at cursor - 1.
        if cursor <= 0 or self.text[cursor - 1] != "@":
            return
        prev = self.text[cursor - 2] if cursor >= 2 else ""
        if prev and not prev.isspace():
            return
        # Defer until after the current event loop tick so the picker
        # mount doesn't fight the change event still in flight.
        self.call_after_refresh(self._open_file_picker)

    def _open_file_picker(self) -> None:
        from veles.tui.screens import FilePickerScreen

        if self.project_root_provider is None:
            return
        root = self.project_root_provider()
        if root is None:
            return
        screen = FilePickerScreen(root)
        self.app.push_screen(screen, self._after_file_pick)

    def _after_file_pick(self, picked: str | None) -> None:
        if not picked:
            return
        # The `@` is already at cursor-1. Insert the path right after it.
        self.insert(picked + " ")

    def action_complete(self) -> None:
        text = self.text
        cursor = self._compute_cursor_offset()
        if self._tab_origin != text or not self._tab_cycle:
            cands = self.completer.candidates(text, cursor)
            if not cands:
                return
            self._tab_cycle = cands
            self._tab_origin = text
            self._tab_index = -1
        self._tab_index = (self._tab_index + 1) % len(self._tab_cycle)
        candidate = self._tab_cycle[self._tab_index]
        # Don't recurse the cycle on the resulting `_replace_text` — the
        # rebuild needs `_tab_origin` to track the candidate so a *second*
        # tab keeps cycling.
        self._replace_text(candidate, keep_tab_cycle=True)
        self._tab_origin = candidate

    def action_launch_editor(self) -> None:
        """Suspend the App, run the user's $EDITOR on the current draft,
        reload its contents on return. Fails gracefully when stdin is
        not a TTY (e.g. inside Pilot run_test)."""
        app = self.app
        if app is None or not _stdin_is_tty():
            return
        editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "vi"
        contents = self.text
        try:
            new_text = _edit_in_editor(editor, contents, runner=_default_subprocess_runner, app=app)
        except Exception:
            return
        if new_text is not None:
            self._replace_text(new_text)

    # ---- helpers ----

    def _replace_text(self, value: str, *, keep_tab_cycle: bool = False) -> None:
        """Assign new text and move the cursor to the end-of-line of the
        last row. The tab-cycle is reset *unless* the caller is the
        cycler itself (it tracks invalidation via `_tab_origin`).

        We don't subscribe to `TextArea.Changed` here. Textual posts
        change events asynchronously, so any in-handler suppression
        flag is racy by the time the listener fires. Instead, the
        cycler compares `text` against the last `_tab_origin` on every
        Tab press — manual edits naturally diverge and trigger a
        rebuild on the next press.
        """
        self.load_text(value)
        # Place cursor at end of last row so a follow-up keypress edits
        # the tail rather than splicing into the middle of a multiline
        # buffer that just loaded.
        last_row = max(0, len(value.splitlines()) - 1)
        self.move_cursor((last_row, 0))
        TextArea.action_cursor_line_end(self)
        if not keep_tab_cycle:
            self._reset_tab_cycle()

    def _reset_tab_cycle(self) -> None:
        self._tab_cycle = []
        self._tab_origin = None
        self._tab_index = -1

    def _compute_cursor_offset(self) -> int:
        """Convert the (row, col) cursor location to a flat offset
        against `self.text`. Used by completers that work on the linear
        string rather than line/col coordinates."""
        try:
            row, col = self.cursor_location
        except AttributeError:
            return len(self.text)
        lines = self.text.splitlines(keepends=True)
        prior = sum(len(line) for line in lines[:row])
        return prior + col


# ---- $EDITOR plumbing ----


def _stdin_is_tty() -> bool:
    import sys

    return bool(sys.stdin and sys.stdin.isatty())


def _veles_tmp_dir() -> Path:
    """Honour the global rule: temp files for our own use land in
    `~/.tmp/` (created on demand) — never the system `/tmp` or the
    macOS `$TMPDIR` directory."""
    root = Path.home() / ".tmp"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _default_subprocess_runner(cmd: list[str]) -> int:
    """Real-process runner. Split off as a seam so tests can patch it
    without monkey-patching subprocess directly."""
    return subprocess.call(cmd)


def _edit_in_editor(
    editor: str,
    initial: str,
    *,
    runner,
    app,
) -> str | None:
    """Write the draft to a tmp file under `~/.tmp/`, run the editor,
    read the result. Returns the new draft, or `None` if the editor
    exited non-zero (caller keeps the original buffer in that case)."""
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".md",
        prefix="veles-composer-",
        dir=_veles_tmp_dir(),
        delete=False,
    ) as fp:
        fp.write(initial)
        tmp_path = Path(fp.name)
    try:
        with app.suspend():
            rc = runner([editor, str(tmp_path)])
        if rc != 0:
            return None
        return tmp_path.read_text(encoding="utf-8")
    finally:
        with contextlib.suppress(OSError):
            tmp_path.unlink()
