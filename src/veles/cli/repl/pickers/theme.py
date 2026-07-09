"""The `/theme` picker mixin for the inline `_ReplApp`.

Mirrors the /model picker but synchronous — `list_themes()` is a dict +
`~/.veles/themes/` glob, no network hop. `_apply_theme_live` restyles the
running Application so a theme switch takes effect immediately. All state
lives on `_ReplApp`.
"""

from __future__ import annotations

from veles.cli.repl.pickers.helpers import _filter_models
from veles.cli.repl.terminal import _resolve_theme
from veles.core.i18n import t


class ThemePickerMixin:
    # --- /theme picker (filterable, driven inside this Application) ---

    # Same window/digit-select shape as the `@` file picker (capped at 9 so
    # 1-9 maps 1:1 onto printed row numbers).
    _TP_WINDOW = 9

    def _open_theme_picker(self) -> None:
        """Populate the candidate list and switch the input box into theming
        mode. Synchronous — `list_themes()` is a dict + `~/.veles/themes/`
        glob, unlike the /model picker's provider fetch, so no executor hop
        needed."""
        from veles.cli.tui_theme import list_themes

        self.tp_active = True
        self.tp_sel = 0
        self.tp_themes = list_themes()
        self.input.text = ""
        self.app.invalidate()

    def _tp_filtered(self) -> list[str]:
        return _filter_models(self.tp_themes, self.input.text)

    def _tp_window_start(self, filtered_len: int) -> int:
        window = self._TP_WINDOW
        if filtered_len <= window:
            return 0
        sel = max(0, min(self.tp_sel, filtered_len - 1))
        return max(0, min(sel - window // 2, filtered_len - window))

    def _tp_fragments(self):
        from prompt_toolkit.formatted_text import FormattedText

        if not self.tp_themes:
            return FormattedText([("class:picker.dim", f" {t('repl.no_themes')}\n")])
        filtered = self._tp_filtered()
        header = t("repl.theme_header", count=len(self.tp_themes))
        frags: list[tuple[str, str]] = [("class:picker", f" {header}\n")]
        if not filtered:
            frags.append(("class:picker.dim", f"  {t('repl.no_matches')}\n"))
            return FormattedText(frags)
        window = self._TP_WINDOW
        start = self._tp_window_start(len(filtered))
        sel = max(0, min(self.tp_sel, len(filtered) - 1))
        for i in range(start, min(start + window, len(filtered))):
            name = filtered[i]
            is_sel = i == sel
            marker = "❯" if is_sel else " "
            row_no = i - start + 1
            cur = "  ← current" if name == self.state.theme_name else ""
            frags.append(
                (
                    "class:picker.sel" if is_sel else "class:picker",
                    f"  {marker} {row_no}. {name}{cur}\n",
                )
            )
        if len(filtered) > window:
            frags.append(("class:picker.dim", f"  {t('repl.more_matches', count=len(filtered))}\n"))
        return FormattedText(frags)

    def _tp_move(self, delta: int) -> None:
        n = len(self._tp_filtered())
        if n:
            self.tp_sel = (max(0, min(self.tp_sel, n - 1)) + delta) % n
        self.app.invalidate()

    def _tp_select_row(self, idx: int) -> None:
        """Digit quick-select: `idx` is 0-based within the CURRENTLY displayed
        window, matching the 1-based row numbers `_tp_fragments` prints."""
        filtered = self._tp_filtered()
        start = self._tp_window_start(len(filtered))
        row = start + idx
        if row < len(filtered):
            self.tp_sel = row
            self.app.invalidate()

    def _apply_theme_live(self) -> None:
        """Rebuild the active `TuiTheme` + prompt_toolkit `Style` from
        `state.theme_name` and assign it to the running Application, so
        SUBSEQUENT rendering (input frame, status bar, future console.print
        calls) picks up the new palette. Already-emitted scrollback can't be
        recoloured — the terminal buffer is immutable, not a bug here."""
        self.theme = _resolve_theme(self.state)
        self.app.style = self._build_style(self.theme)
        self.app.invalidate()

    def _tp_pick(self) -> None:
        filtered = self._tp_filtered()
        if not filtered:
            return
        name = filtered[max(0, min(self.tp_sel, len(filtered) - 1))]
        self.state.theme_name = name  # subsequent turns/renders read this fresh
        self._apply_theme_live()

        import contextlib

        from veles.core.user_config import persist_tui_theme

        with contextlib.suppress(Exception):
            persist_tui_theme(name)
        self._tp_close()
        self.console.print(f"  ⋅ theme set to {name}", style=self.theme.muted, markup=False)

    def _tp_cancel(self) -> None:
        self._tp_close()
        self.console.print(f"  ⋅ {t('repl.theme_cancelled')}", style=self.theme.muted, markup=False)

    def _tp_close(self) -> None:
        self.tp_active = False
        self.tp_themes = []
        self.input.text = ""
        self.app.invalidate()
