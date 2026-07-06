"""The status bar + live-generation HUD + picker-fragment rendering for
the inline `_ReplApp`.

`_status_fragments` is the quiet settled bottom bar; `_meta_fragments` is
the "working…" HUD (elapsed, approximate token count, tool/mode activity);
`_picker_fragments` renders the mid-turn ask_user/permission picker;
`_push_meta`/`_tick_meta` feed and animate the HUD; `_build_style` builds
the prompt_toolkit `Style` from the theme. All state lives on `_ReplApp`.
"""

from __future__ import annotations

import asyncio
import time

from veles.cli.repl.terminal import _settled_status, _tool_row
from veles.core.i18n import t


class HudMixin:
    def _status_fragments(self):
        # The quiet bottom bar: settled mode + tokens + cache ONLY (no live
        # churn — the working HUD carries the per-request counters).
        return [
            (
                "class:status",
                f" {_settled_status(self.state)} · Shift+Tab mode · /help · "
                "Ctrl+O/I meta · Ctrl+D exit ",
            )
        ]

    def _meta_fragments(self):
        """The generation HUD in the app region: elapsed, an approximate
        output-token count (chars/4 — providers only report exact usage in the
        final chunk), and tool/mode-switch activity. Reads "working…" while the
        turn runs and "done" once it finishes (the block stays until the next
        prompt). Collapsed by default; Ctrl+O expands the event list, and the
        toggle works in both states because the block is visible in both."""
        from prompt_toolkit.formatted_text import FormattedText

        approx = self.stream_chars // 4
        tools = [t for k, t in self.meta_events if k == "tool"]
        modes = [t for k, t in self.meta_events if k == "mode"]
        # Live while the turn runs; FROZEN once done (else every idle re-render
        # recomputes now - turn_start and the "done" line keeps ticking up).
        if self.busy:
            elapsed = int(time.monotonic() - self.turn_start) if self.turn_start else 0
        else:
            elapsed = int(self.turn_elapsed)
        label = f" ⏳ working{'.' * (1 + (self._tick % 3))}" if self.busy else " ✓ done"
        head = f"{label} · ≈{approx} tok · {len(tools)} tool(s) · {elapsed}s"
        hint = t("repl.meta_collapse") if self.meta_expanded else t("repl.meta_expand")
        frags: list[tuple[str, str]] = [("class:meta", head + hint + "\n")]
        if self.meta_expanded:
            for mode in modes:
                frags.append(("class:meta.dim", f"     ↳ {mode}\n"))
            if self.tool_activity:
                for rec in list(self.tool_activity.values())[-10:]:
                    frags.append(("class:meta.dim", f"     {_tool_row(rec)}\n"))
            else:
                # Plain tool labels pushed with no tool_call_id (e.g. direct
                # `_push_meta("tool", ...)` calls) — no status/duration to show.
                for tl in tools[-10:]:
                    frags.append(("class:meta.dim", f"     ⚒ {tl}\n"))
        return FormattedText(frags)

    def _picker_fragments(self):
        """The mid-turn picker (ask_user or permission) rendered in the app
        region. The free-text row shows only when q_allow_free (ask_user)."""
        from prompt_toolkit.formatted_text import FormattedText

        frags: list[tuple[str, str]] = [("class:picker", f" {self.q_question}\n")]
        if self.q_free:
            frags.append(("class:picker.dim", f"  {t('repl.free_input_hint')}\n"))
            return FormattedText(frags)
        items = [*self.q_options] + ([t("repl.free_choice")] if self.q_allow_free else [])
        for i, label in enumerate(items):
            sel = i == self.q_sel
            marker = "❯" if sel else " "
            frags.append(("class:picker.sel" if sel else "class:picker", f"  {marker} {label}\n"))
        frags.append(("class:picker.dim", f"  {t('repl.picker_hint')}\n"))
        return FormattedText(frags)

    def _push_meta(
        self, kind: str, text: str, *, tool_call_id: str = "", error: str | None = None
    ) -> None:
        """Meta sink for the turn callbacks (called from the executor thread).

        `tool_call_id`/`error` are only meaningful for the "tool"/"tool_result"
        kinds and drive `self.tool_activity`, the inspector's per-tool
        running/done/failed + duration state (Ctrl+I/Ctrl+O expanded view)."""
        if kind == "stream":
            self.stream_chars += len(text)
        elif kind == "tool_result":
            rec = self.tool_activity.get(tool_call_id)
            if rec is not None:
                rec["end"] = time.monotonic()
                rec["status"] = "failed" if error else "done"
        else:
            self.meta_events.append((kind, text))
            if kind == "tool" and tool_call_id:
                self.tool_activity[tool_call_id] = {
                    "name": text,
                    "start": time.monotonic(),
                    "end": None,
                    "status": "running",
                }
        self._invalidate_threadsafe()

    async def _tick_meta(self) -> None:
        """Animate the HUD's spinner/elapsed while a turn runs."""
        while self.busy:
            self._tick += 1
            self.app.invalidate()
            await asyncio.sleep(0.3)

    def _build_style(self, theme):
        """The prompt_toolkit `Style` built from `theme`. Shared by `__init__`
        (initial render) and `_apply_theme_live` (`/theme` restyles the running
        Application) so the two never drift."""
        from prompt_toolkit.styles import Style

        return Style.from_dict(
            {
                "frame.border": theme.border,
                "prompt": f"bold {theme.accent}",
                "status": theme.muted,
                "meta": theme.accent,
                "meta.dim": theme.muted,
                "picker": "",  # normal item — inherit the terminal foreground
                "picker.sel": theme.pt_selected,
                "picker.dim": theme.pt_hint,
            }
        )
