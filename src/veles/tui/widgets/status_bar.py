"""One-line footer: session id, provider/model, busy indicator, queue
depth, plus M79 token + context-window meter."""

from __future__ import annotations

from textual.widgets import Static

from veles.core.model_naming import strip_provider_prefix
from veles.tui.state import AppState

# Conservative defaults; refined per-model via `_context_limit_for`.
_DEFAULT_CTX_LIMIT = 200_000


def _fmt_tokens(n: int) -> str:
    if n < 1_000:
        return str(n)
    if n < 1_000_000:
        return f"{n / 1_000:.1f}k".rstrip("0").rstrip(".") + "k" if False else f"{n // 1_000}k"
    return f"{n // 1_000_000}M"


def _context_limit_for(model: str | None) -> int:
    """Best-effort context-window lookup. Real per-model limits live in
    the adapter; here we approximate by model-id substring so the status
    bar shows a sensible % when adapter metadata is unavailable."""
    if not model:
        return _DEFAULT_CTX_LIMIT
    m = model.lower()
    if "claude" in m or "sonnet" in m or "opus" in m or "haiku" in m:
        return 200_000
    if "gpt-4o" in m or "gpt-4.1" in m:
        return 128_000
    if "gemini" in m and "1.5" in m:
        return 1_000_000
    if "gemini" in m:
        return 200_000
    return _DEFAULT_CTX_LIMIT


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
    if not state.last_turn_total_tokens:
        return None
    limit = _context_limit_for(state.model)
    pct = (state.last_turn_total_tokens * 100) // max(limit, 1)
    marker = "[bold red]" if pct >= 80 else ("[yellow]" if pct >= 60 else "")
    close = "[/]" if marker else ""
    return (
        f"ctx {marker}{_fmt_tokens(state.last_turn_total_tokens)}/"
        f"{_fmt_tokens(limit)} ({pct}%){close}"
    )


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
