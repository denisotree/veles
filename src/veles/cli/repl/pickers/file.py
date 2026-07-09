"""The `@` file-reference picker mixin for the inline `_ReplApp`.

Triggered inline by typing `@` at a word boundary (not a slash command);
unlike the /model picker it keeps the `@`+filter text IN the input box
(Enter re-inserts a path after the `@`). Synchronous — `iter_project_files`
is a plain filesystem walk. All state lives on `_ReplApp`.
"""

from __future__ import annotations

from pathlib import Path

from veles.cli.repl.pickers.helpers import _filter_files
from veles.core.i18n import t


class FilePickerMixin:
    # --- @ file picker (filterable, triggered inline by typing `@`) ---

    # Rows shown at once — capped at 9 so digit quick-select (1-9) maps
    # 1:1 onto the printed row numbers, mirroring the ask_user picker.
    _FP_WINDOW = 9

    def _open_file_picker(self, root: Path | None = None) -> None:
        """Populate the candidate list and switch the input box into filing
        mode. Synchronous — `iter_project_files` is a plain filesystem walk,
        unlike the /model picker's network fetch, so no executor hop needed."""
        from veles.cli.repl.file_index import iter_project_files

        self.fp_active = True
        self.fp_sel = 0
        try:
            self.fp_files = [p.as_posix() for p in iter_project_files(root or self.project.root)]
        except OSError:
            self.fp_files = []
        self.app.invalidate()

    def _fp_filter_text(self) -> str:
        """The filter is whatever follows the LAST `@` before the cursor —
        the `@` itself (and anything before it) stays put while filtering,
        and anything after the cursor (e.g. the rest of a multi-line
        Alt+Enter-composed message) is ignored rather than pollute the
        filter token."""
        before_cursor = self.input.buffer.document.text_before_cursor
        idx = before_cursor.rfind("@")
        return before_cursor[idx + 1 :] if idx != -1 else ""

    def _fp_filtered(self) -> list[str]:
        return _filter_files(self.fp_files, self._fp_filter_text())

    def _fp_window_start(self, filtered_len: int) -> int:
        window = self._FP_WINDOW
        if filtered_len <= window:
            return 0
        sel = max(0, min(self.fp_sel, filtered_len - 1))
        return max(0, min(sel - window // 2, filtered_len - window))

    def _fp_fragments(self):
        from prompt_toolkit.formatted_text import FormattedText

        if not self.fp_files:
            return FormattedText([("class:picker.dim", f" {t('repl.no_files')}\n")])
        filtered = self._fp_filtered()
        header = t("repl.file_header", count=len(self.fp_files))
        frags: list[tuple[str, str]] = [("class:picker", f" {header}\n")]
        if not filtered:
            frags.append(("class:picker.dim", f"  {t('repl.no_matches')}\n"))
            return FormattedText(frags)
        window = self._FP_WINDOW
        start = self._fp_window_start(len(filtered))
        sel = max(0, min(self.fp_sel, len(filtered) - 1))
        for i in range(start, min(start + window, len(filtered))):
            path = filtered[i]
            is_sel = i == sel
            marker = "❯" if is_sel else " "
            row_no = i - start + 1
            frags.append(
                ("class:picker.sel" if is_sel else "class:picker", f"  {marker} {row_no}. {path}\n")
            )
        if len(filtered) > window:
            frags.append(("class:picker.dim", f"  {t('repl.more_matches', count=len(filtered))}\n"))
        return FormattedText(frags)

    def _fp_move(self, delta: int) -> None:
        n = len(self._fp_filtered())
        if n:
            self.fp_sel = (max(0, min(self.fp_sel, n - 1)) + delta) % n
        self.app.invalidate()

    def _fp_select_row(self, idx: int) -> None:
        """Digit quick-select: `idx` is 0-based within the CURRENTLY displayed
        window, matching the 1-based row numbers `_fp_fragments` prints."""
        filtered = self._fp_filtered()
        start = self._fp_window_start(len(filtered))
        row = start + idx
        if row < len(filtered):
            self.fp_sel = row
            self.app.invalidate()

    def _fp_pick(self) -> None:
        filtered = self._fp_filtered()
        if not filtered:
            return
        path = filtered[max(0, min(self.fp_sel, len(filtered) - 1))]
        doc = self.input.buffer.document
        before, after = doc.text_before_cursor, doc.text_after_cursor
        idx = before.rfind("@")
        prefix = before[:idx] if idx != -1 else before
        # Preserve whatever came after the cursor verbatim (e.g. the rest of
        # a multi-line message) instead of truncating it.
        new_text = f"{prefix}@{path}{after}"
        self.input.text = new_text
        self.input.buffer.cursor_position = len(prefix) + 1 + len(path)
        self._fp_close()

    def _fp_cancel(self) -> None:
        self._fp_close()

    def _fp_close(self) -> None:
        self.fp_active = False
        self.fp_files = []
        self.app.invalidate()
