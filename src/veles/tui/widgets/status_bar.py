"""One-line footer: session id, provider/model, busy indicator, queue
depth, plus M79 token + context-window meter."""

from __future__ import annotations

from textual.widgets import Static

from veles.core.model_naming import strip_provider_prefix
from veles.core.model_windows import context_window_for
from veles.tui.state import AppState


def _fmt_tokens(n: int) -> str:
    if n < 1_000:
        return str(n)
    if n < 1_000_000:
        return f"{n / 1_000:.1f}k".rstrip("0").rstrip(".") + "k" if False else f"{n // 1_000}k"
    return f"{n // 1_000_000}M"


# ---- per-chip renderers ----
#
# Each `_chip_*` returns the rendered string, or None when the chip is
# off for the current state. `_collect_chips` chains them in display
# order. Splitting per-chip keeps `render_state` short and lets the
# test suite hit edge cases without driving the whole AppState.


def _chip_mode(state: AppState) -> str:
    """Sticky preference shown first — user toggles via Shift+Tab."""
    return f"[{state.mode}]"


def _chip_session(state: AppState) -> str:
    return f"session {state.session_id or 'new'}"


def _chip_provider_model(state: AppState) -> str:
    """`<provider>/<model>` with a leading known-provider stripped from
    `state.model` (M107) so we never render `openai/openrouter/...`."""
    return f"{state.provider_name}/{strip_provider_prefix(state.model)}"


def _chip_tokens(state: AppState) -> str | None:
    if not (state.tokens_in or state.tokens_out):
        return None
    return f"tok {_fmt_tokens(state.tokens_in)}/{_fmt_tokens(state.tokens_out)}"


def _chip_context(state: AppState) -> str | None:
    """Live context occupancy: the last request's prompt size vs the model
    window. M177 — this used to render cumulative run usage
    (`last_turn_total_tokens`) over a hardcoded 200k, which conflated billed
    tokens with window size and could show >100%. The prompt-size proxy is
    what's actually resident for the next turn, so the % stays sane."""
    occupied = state.last_prompt_tokens or state.last_turn_total_tokens
    if not occupied:
        return None
    limit = context_window_for(state.model)
    pct = (occupied * 100) // max(limit, 1)
    marker = "[bold red]" if pct >= 80 else ("[yellow]" if pct >= 60 else "")
    close = "[/]" if marker else ""
    return f"ctx {marker}{_fmt_tokens(occupied)}/{_fmt_tokens(limit)} ({pct}%){close}"


def _chip_insights(state: AppState) -> str | None:
    if not state.insight_candidates:
        return None
    return f"[bold cyan]{len(state.insight_candidates)} insight(s)[/]"


def _chip_busy(state: AppState) -> str | None:
    return "[bold]busy[/bold]" if state.busy else None


def _chip_queue(state: AppState) -> str | None:
    return f"queue {len(state.queue)}" if state.queue else None


def _collect_chips(state: AppState) -> list[str]:
    """Run every chip renderer in display order and drop the None's."""
    chips = (
        _chip_mode(state),
        _chip_session(state),
        _chip_provider_model(state),
        _chip_tokens(state),
        _chip_context(state),
        _chip_insights(state),
        _chip_busy(state),
        _chip_queue(state),
    )
    return [c for c in chips if c is not None]


class StatusBar(Static):
    # Lets Textual's selection API target the chips (Shift+arrow keyboard
    # selection, copy-on-selection on terminals with clipboard access).
    # Native terminal drag-select + system ⌘C also works because mouse
    # reporting is off (see `veles.tui.run_tui`).
    allow_select = True

    DEFAULT_CSS = """
    StatusBar {
        background: $primary 20%;
        color: $text;
        padding: 0 1;
        height: 1;
        dock: bottom;
    }
    """

    def __init__(self) -> None:
        super().__init__("", id="veles-status-bar")
        # Plain-text shadow of whatever was last passed to `update`. Lets
        # tests assert against status content without poking into
        # Textual's internal `Static.content`/`render()` shape, which
        # varies across versions.
        self.last_text: str = ""

    def render_state(self, state: AppState) -> None:
        text = " · ".join(_collect_chips(state))
        self.last_text = text
        self.update(text)
