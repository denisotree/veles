"""The `/model` picker mixin for the inline `_ReplApp`.

Filterable, driven inside the running Application: the input box is the
live filter. The catalogue fetch (cold cache / `refresh` does network I/O)
runs in an executor so it never blocks the event loop. All state lives on
`_ReplApp`.
"""

from __future__ import annotations

import asyncio

from veles.cli.repl.pickers.helpers import _filter_models
from veles.core.i18n import t


class ModelPickerMixin:
    # --- /model picker (filterable, driven inside this Application) ---

    def _open_model_picker(self, refresh: bool = False) -> None:
        self.mp_active = True
        self.mp_loading = True
        self.mp_models = []
        self.mp_source = ""
        self.mp_sel = 0
        self.input.text = ""
        self.app.invalidate()

        async def _load() -> None:
            loop = asyncio.get_event_loop()
            models, source = await loop.run_in_executor(None, self._fetch_models, refresh)
            if self.mp_active:  # not cancelled while the fetch was in flight
                self.mp_models = models
                self.mp_source = source
                self.mp_loading = False
                self.mp_sel = 0
                self.app.invalidate()

        self._spawn(_load())

    def _fetch_models(self, refresh: bool):
        """Runs in the executor (a refresh / cold cache does network I/O, which
        must not block the event loop). Returns (models, source)."""
        from veles.cli.repl.model_fetcher import fetch_models

        try:
            result = fetch_models(self.state.provider_name, refresh=refresh)
            return result.models, result.source
        except Exception:
            return [], "error"

    def _mp_filtered(self) -> list[str]:
        return _filter_models(self.mp_models, self.input.text)

    def _mp_fragments(self):
        from prompt_toolkit.formatted_text import FormattedText

        if self.mp_loading:
            return FormattedText(
                [
                    (
                        "class:picker",
                        f" {t('repl.loading_models', provider=self.state.provider_name)}\n",
                    )
                ]
            )
        if not self.mp_models:
            return FormattedText([("class:picker.dim", f" {t('repl.no_models')}\n")])
        filtered = self._mp_filtered()
        header = t(
            "repl.model_header",
            provider=self.state.provider_name,
            count=len(self.mp_models),
            source=self.mp_source,
        )
        head = f" {header}\n"
        frags: list[tuple[str, str]] = [("class:picker", head)]
        if not filtered:
            frags.append(("class:picker.dim", f"  {t('repl.no_matches')}\n"))
            return FormattedText(frags)
        sel = max(0, min(self.mp_sel, len(filtered) - 1))
        window = 10
        start = (
            max(0, min(sel - window // 2, len(filtered) - window)) if len(filtered) > window else 0
        )
        for i in range(start, min(start + window, len(filtered))):
            m = filtered[i]
            is_sel = i == sel
            marker = "❯" if is_sel else " "
            cur = "  ← current" if m == self.state.model else ""
            frags.append(
                ("class:picker.sel" if is_sel else "class:picker", f"  {marker} {m}{cur}\n")
            )
        if len(filtered) > window:
            frags.append(("class:picker.dim", f"  {t('repl.more_matches', count=len(filtered))}\n"))
        return FormattedText(frags)

    def _mp_move(self, delta: int) -> None:
        n = len(self._mp_filtered())
        if n:
            self.mp_sel = (max(0, min(self.mp_sel, n - 1)) + delta) % n
        self.app.invalidate()

    def _mp_pick(self) -> None:
        filtered = self._mp_filtered()
        if not filtered:
            return
        model = filtered[max(0, min(self.mp_sel, len(filtered) - 1))]
        self.state.model = model  # the factory reads state.model fresh next turn
        import contextlib

        from veles.core.tui_state import persist_model_choice

        with contextlib.suppress(Exception):
            persist_model_choice(self.project, model)
        self._mp_close()
        self.console.print(f"  ⋅ model set to {model}", style=self.theme.muted, markup=False)

    def _mp_cancel(self) -> None:
        self._mp_close()
        self.console.print(f"  ⋅ {t('repl.model_cancelled')}", style=self.theme.muted, markup=False)

    def _mp_close(self) -> None:
        self.mp_active = False
        self.mp_loading = False
        self.mp_models = []
        self.input.text = ""
        self.app.invalidate()
