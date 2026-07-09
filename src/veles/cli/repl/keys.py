"""Key bindings + input-driven handlers for the inline `_ReplApp`.

Builds the prompt_toolkit `KeyBindings` (the regime-gated Enter/arrow/digit
handlers for the normal prompt and each picker, Shift+Tab mode cycle, the
Ctrl+O/I inspector toggle, Ctrl+X Ctrl+E editor, Ctrl+V paste, Ctrl+C/D),
plus the submit / Ctrl+C / Esc-cancel handlers, the input-changed filter
hook, and the Ctrl+V image paste. All state lives on `_ReplApp`; cross-mixin
methods (`_spawn`, `_dispatch`, `_history_up/_down`, the picker moves) are
reached through `self` via the MRO.
"""

from __future__ import annotations

import sys
import time

from veles.cli.repl.pickers.helpers import _at_trigger_boundary, _new_paste_filename
from veles.cli.repl.terminal import _CTRL_C_EXIT_WINDOW_S


class KeysMixin:
    # --- /model picker (filterable, driven inside this Application) ---

    def _on_input_changed(self, _buffer) -> None:
        # While the model picker is open the input box is the filter; reset the
        # highlighted row to the top on each keystroke so the selection tracks
        # the freshly-filtered list.
        if self.mp_active:
            self.mp_sel = 0
            self.app.invalidate()
        if self.fp_active:
            # The `@` file picker shares the box with regular typing (the `@`
            # + filter text stays in the prompt) — if the user backspaces past
            # the `@` that opened it, close quietly rather than filtering "".
            if "@" not in self.input.text:
                self._fp_close()
            else:
                self.fp_sel = 0
                self.app.invalidate()
        if self.tp_active:
            self.tp_sel = 0
            self.app.invalidate()

    # --- Ctrl+V image paste (M187 Task 7) ---

    def _paste_clipboard(self) -> None:
        """An image on the clipboard is saved under `.veles/tmp/paste/` and
        referenced via `@<relative-path>` inserted at the cursor — the same
        reference syntax the `@` file picker inserts. Falls back to a plain
        text paste when the clipboard holds no image. Both clipboard ops are
        best-effort (see `cli/repl/clipboard.py`) and no-op silently when the
        platform/tooling doesn't support them. Same no-TTY guard as `_ask`/
        `_confirm_critical` so a headless run degrades instead of hanging."""
        from veles.cli.repl.clipboard import paste_image, paste_text

        if not sys.stdin.isatty():
            return
        paste_dir = self.project.tmp_dir / "paste"
        target = paste_dir / _new_paste_filename()
        if paste_image(target):
            try:
                rel = target.relative_to(self.project.root).as_posix()
            except ValueError:
                rel = target.as_posix()
            doc = self.input.buffer.document
            before, after = doc.text_before_cursor, doc.text_after_cursor
            ref = f"@{rel} "
            self.input.text = f"{before}{ref}{after}"
            self.input.buffer.cursor_position = len(before) + len(ref)
            return
        text = paste_text()
        if text:
            # Same document-splice shape as the image-ref branch above (and
            # `_fp_pick`) rather than `Buffer.insert_text` — that path also
            # kicks off the completer's background task, which needs a
            # running Application event loop.
            doc = self.input.buffer.document
            before, after = doc.text_before_cursor, doc.text_after_cursor
            self.input.text = f"{before}{text}{after}"
            self.input.buffer.cursor_position = len(before) + len(text)

    def _make_keys(self):
        from prompt_toolkit.filters import Condition
        from prompt_toolkit.key_binding import KeyBindings

        kb = KeyBindings()
        # Input regimes, gated by filters so one key means different things:
        #   normal   — typing a prompt (no picker up)
        #   choosing — arrow-selecting an ask_user option
        #   freeing  — typing a free-text answer to an ask_user question
        #   modeling — filtering/selecting in the /model picker
        #   filing   — filtering/selecting in the @ file picker
        #   theming  — filtering/selecting in the /theme picker
        normal = Condition(
            lambda: (
                not self.q_active
                and not self.mp_active
                and not self.fp_active
                and not self.tp_active
            )
        )
        choosing = Condition(lambda: self.q_active and not self.q_free)
        freeing = Condition(lambda: self.q_active and self.q_free)
        modeling = Condition(lambda: self.mp_active)
        filing = Condition(lambda: self.fp_active)
        theming = Condition(lambda: self.tp_active)

        @kb.add("enter", filter=normal)
        def _(event) -> None:
            self._on_enter()

        @kb.add("enter", filter=choosing)
        def _(event) -> None:
            self._picker_enter()

        @kb.add("enter", filter=freeing)
        def _(event) -> None:
            self._free_submit()

        # Alt/Option+Enter → newline. NOT while busy: an active escape-prefix
        # binding makes a lone Esc a pending prefix, so Esc-to-stop-generation
        # would never resolve. During a turn you're queuing, not composing.
        @kb.add(
            "escape",
            "enter",
            filter=Condition(
                lambda: (
                    not self.q_active
                    and not self.mp_active
                    and not self.fp_active
                    and not self.tp_active
                    and not self.busy
                )
            ),
        )
        def _(event) -> None:
            self.input.buffer.insert_text("\n")

        @kb.add("c-j", filter=normal)  # Ctrl+J = LF (0x0a) — a newline key that
        def _(event) -> None:  # is distinct from Enter (0x0d) in EVERY terminal,
            self.input.buffer.insert_text("\n")  # unlike Shift+Enter.

        @kb.add("f24", filter=normal)  # Shift+Enter (CSI-u terminals) → newline
        def _(event) -> None:
            self.input.buffer.insert_text("\n")

        @kb.add("up", filter=normal)
        def _(event) -> None:
            self._history_up()

        @kb.add("down", filter=normal)
        def _(event) -> None:
            self._history_down()

        @kb.add("@", filter=normal)
        def _(event) -> None:
            # Type the `@` as usual, then — only at a word boundary (start of
            # input / after whitespace) — open the file picker. Mid-word (an
            # email address) it's just a character. Never open while a turn is
            # running (`busy`): a mid-turn `_ask`/`_permission_prompt` can flip
            # `q_active` on top of an already-open picker, putting two
            # mutually-exclusive filter states active at once.
            before = self.input.buffer.document.text_before_cursor
            boundary = _at_trigger_boundary(before)
            self.input.buffer.insert_text("@")
            if boundary and not self.busy:
                self._open_file_picker()

        @kb.add("up", filter=choosing)
        def _(event) -> None:
            self.q_sel = (self.q_sel - 1) % self._picker_rows()
            self.app.invalidate()

        @kb.add("down", filter=choosing)
        def _(event) -> None:
            self.q_sel = (self.q_sel + 1) % self._picker_rows()
            self.app.invalidate()

        for _i in range(9):

            @kb.add(str(_i + 1), filter=choosing)
            def _(event, idx=_i) -> None:
                if idx < self._picker_rows():
                    self.q_sel = idx
                    self.app.invalidate()

        @kb.add("escape", filter=Condition(lambda: self.q_active))
        def _(event) -> None:
            self._answer(None)

        @kb.add(
            "escape",
            filter=Condition(
                lambda: (
                    self.busy
                    and not self.q_active
                    and not self.mp_active
                    and not self.fp_active
                    and not self.tp_active
                )
            ),
        )
        def _(event) -> None:  # Esc during generation → stop + restore the request
            self._cancel_generation()

        @kb.add("enter", filter=modeling)
        def _(event) -> None:
            self._mp_pick()

        @kb.add("up", filter=modeling)
        def _(event) -> None:
            self._mp_move(-1)

        @kb.add("down", filter=modeling)
        def _(event) -> None:
            self._mp_move(1)

        @kb.add("escape", filter=modeling)
        def _(event) -> None:
            self._mp_cancel()

        @kb.add("enter", filter=filing)
        def _(event) -> None:
            self._fp_pick()

        @kb.add("up", filter=filing)
        def _(event) -> None:
            self._fp_move(-1)

        @kb.add("down", filter=filing)
        def _(event) -> None:
            self._fp_move(1)

        @kb.add("escape", filter=filing)
        def _(event) -> None:
            self._fp_cancel()

        for _i in range(9):

            @kb.add(str(_i + 1), filter=filing)
            def _(event, idx=_i) -> None:
                self._fp_select_row(idx)

        @kb.add("enter", filter=theming)
        def _(event) -> None:
            self._tp_pick()

        @kb.add("up", filter=theming)
        def _(event) -> None:
            self._tp_move(-1)

        @kb.add("down", filter=theming)
        def _(event) -> None:
            self._tp_move(1)

        @kb.add("escape", filter=theming)
        def _(event) -> None:
            self._tp_cancel()

        for _i in range(9):

            @kb.add(str(_i + 1), filter=theming)
            def _(event, idx=_i) -> None:
                self._tp_select_row(idx)

        @kb.add("s-tab", filter=normal)
        def _(event) -> None:
            self.state.mode = self._next_mode(self.state.mode)
            self.app.invalidate()

        @kb.add("c-o")
        def _(event) -> None:
            self.meta_expanded = not self.meta_expanded
            self.app.invalidate()

        # Ctrl+I IS Tab in prompt_toolkit (same key code) — gate the inspector
        # toggle so it only fires when no completion menu is open. Otherwise it
        # shadows the default Tab binding that cycles slash-command completions
        # (docs/en/reference/tui.md), since this Application's own bindings take
        # priority over prompt_toolkit's merged defaults. (M187 regression fix.)
        @kb.add("c-i", filter=Condition(lambda: self.input.buffer.complete_state is None))
        def _(event) -> None:
            self.meta_expanded = not self.meta_expanded
            self.app.invalidate()

        # $EDITOR compose (M187 Task 7): prompt_toolkit ships an emacs
        # `c-x c-e` -> `Buffer.open_in_editor()` binding via
        # `load_open_in_editor_bindings()`, but this Application's default
        # bindings come from `load_key_bindings()` (key_binding/defaults.py),
        # which does NOT merge that one in — so `c-x c-e` does nothing here
        # out of the box. We wire it ourselves, straight onto the input
        # buffer, rather than merging in the stock bindings (keeps one
        # KeyBindings object to reason about). No collision: neither the
        # emacs `c-x` prefix map (`c-u`/`r y`/`(`/`)`/`e`/`c-x` as the second
        # key — see `key_binding/bindings/emacs.py`) nor any binding of ours
        # uses "c-e" as the second key of a `c-x` chord. Same no-TTY guard as
        # `_ask`/`_confirm_critical` so a headless run/test degrades to a
        # no-op instead of hanging on a real editor subprocess spawn.
        @kb.add("c-x", "c-e", filter=normal)
        def _(event) -> None:
            if not sys.stdin.isatty():
                return
            self.input.buffer.open_in_editor()

        # Image paste (M187 Task 7). Deliberately NOT Ctrl+G — the old
        # Textual composer's binding — because Ctrl+G is prompt_toolkit's
        # DEFAULT abort/keyboard-quit (`c-g` in both `basic.py` and
        # `emacs.py`: cancel-selection / abort-incremental-search). Left
        # unbound here so that default keeps working. Ctrl+V has no default
        # binding that matters in this Application: `basic.py`'s `c-v` is a
        # no-op placeholder, and the emacs `c-v` -> scroll-page-down only
        # activates under `enable_page_navigation_bindings`, which is gated
        # on `full_screen` — this Application passes `full_screen=False`.
        @kb.add("c-v", filter=normal)
        def _(event) -> None:
            self._paste_clipboard()

        @kb.add("c-d")
        def _(event) -> None:
            event.app.exit()

        @kb.add("c-c")
        def _(event) -> None:
            self._on_ctrl_c(event)

        return kb

    def _on_enter(self) -> None:
        raw = self.input.text
        text = raw.strip()
        self.input.text = ""
        if not text:
            self._hist_pos = None
            return  # ignore empty input
        self._record_history(raw)
        self._spawn(self._dispatch(text))

    def _on_ctrl_c(self, event) -> None:
        if self.tp_active:
            self._tp_cancel()  # cancel the /theme picker
            return
        if self.fp_active:
            self._fp_cancel()  # cancel the @ file picker
            return
        if self.mp_active:
            self._mp_cancel()  # cancel the /model picker
            return
        if self.q_active:
            self._answer(None)  # cancel the pending question
            return
        if self.busy and self.cancel_token is not None:
            if self.cancel_token.cancelled:
                # A cancel was already requested and the turn still hasn't
                # stopped (a truly wedged call the cooperative path can't reach).
                # Escape hatch: force-quit so the chat is never a dead end.
                self._force_quit()
                return
            self.cancel_token.cancel()  # cooperative cancel of the running turn
            self._spawn(
                self._in_terminal(
                    lambda: self.console.print(
                        "(cancelling… press Ctrl+C again to force-quit)",
                        style=self.theme.muted,
                    )
                )
            )
            return
        if self.input.text:
            self.input.text = ""  # clear the current line
            return
        now = time.monotonic()
        if now - self._last_ctrl_c <= _CTRL_C_EXIT_WINDOW_S:
            event.app.exit()
            return
        self._last_ctrl_c = now
        self._spawn(
            self._in_terminal(
                lambda: self.console.print(
                    "(Ctrl+C again or Ctrl+D to exit)", style=self.theme.muted
                )
            )
        )

    def _force_quit(self) -> None:
        """Last-resort escape from a wedged turn (a call the cooperative cancel
        can't reach). Restore the terminal, then hard-exit — `os._exit` bypasses
        the ThreadPoolExecutor's atexit join, which would otherwise hang forever
        on the blocked provider call. Skips normal cleanup by design; this only
        runs when the user has already asked to cancel and it didn't take."""
        import os

        from veles.cli.repl.terminal import _kitty_disable_keyboard

        try:
            _kitty_disable_keyboard()
            sys.stdout.write("\x1b[?25h\r\n")  # show cursor, fresh line
            sys.stdout.flush()
        except Exception:
            pass
        os._exit(130)

    def _cancel_generation(self) -> None:
        """Esc while a turn runs: stop it *now*. Cancelling the token both
        unwinds the agent loop (at its next ~100ms check) and instantly gates
        the output callbacks (see `_make_turn_callbacks` `stop_check`), so
        visible generation halts immediately. The request text is dropped back
        into the input box for editing ONLY when nothing was generated yet;
        once the answer has started streaming, Esc is a plain stop. Also clears
        the queue so Esc fully stops (not just the current turn)."""
        if self.cancel_token is not None:
            self.cancel_token.cancel()  # stop the turn + gate its output at once
        self.queue.clear()  # a full stop — don't run queued follow-ups
        if self.stream_chars == 0 and self._last_submitted:
            self._set_input(self._last_submitted)  # restore only before first output
        self.app.invalidate()
