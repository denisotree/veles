"""Up/Down input-history recall for the inline REPL.

There used to be a second implementation here, `InputHistory` — the Textual
Composer's history, persisted to `~/.veles/tui_history.jsonl`. It lost its only
caller when the Textual chat UI was deleted (M187) and survived another two
months imported by nothing but its own test, while `HistoryMixin` below did the
same job for the REPL. Removed so there is one history, not two.
"""

from __future__ import annotations


class HistoryMixin:
    """Explicit Up/Down input-history recall for the inline `_ReplApp`.

    The `Buffer`'s own async `FileHistory` didn't resync a just-submitted
    command in this embedded Application (Up recalled stale entries), so the
    REPL keeps a plain oldest→newest list, persists to the same
    `repl_history` file, and drives Up/Down itself. All state (`_hist`,
    `_hist_store`, `_hist_pos`, `_hist_draft`) lives on `_ReplApp`.
    """

    # --- input history (explicit; the Buffer's async FileHistory didn't resync
    # a just-submitted command in this embedded Application) ---

    def _record_history(self, text: str) -> None:
        """Append a submitted command to the in-memory history and persist it to
        the shared `repl_history` file. Skips a consecutive duplicate. Resets the
        recall cursor so the next Up starts from the newest entry."""
        text = text.rstrip("\n")
        if text and (not self._hist or self._hist[-1] != text):
            self._hist.append(text)
            import contextlib

            with contextlib.suppress(Exception):
                self._hist_store.store_string(text)  # cross-run persistence
        self._hist_pos = None

    def _set_input(self, text: str) -> None:
        self.input.text = text
        self.input.buffer.cursor_position = len(text)  # cursor at end of recall

    def _history_up(self) -> None:
        # Multiline: move the cursor up within the text unless already on the
        # first row — only then recall an older command.
        doc = self.input.buffer.document
        if doc.cursor_position_row > 0:
            self.input.buffer.cursor_up()
            return
        if not self._hist:
            return
        if self._hist_pos is None:  # starting recall — stash the draft line
            self._hist_draft = self.input.text
            self._hist_pos = len(self._hist)
        if self._hist_pos > 0:
            self._hist_pos -= 1
            self._set_input(self._hist[self._hist_pos])

    def _history_down(self) -> None:
        doc = self.input.buffer.document
        if doc.cursor_position_row < doc.line_count - 1:
            self.input.buffer.cursor_down()
            return
        if self._hist_pos is None:
            return
        self._hist_pos += 1
        if self._hist_pos >= len(self._hist):  # past the newest → restore draft
            self._hist_pos = None
            self._set_input(self._hist_draft)
        else:
            self._set_input(self._hist[self._hist_pos])
