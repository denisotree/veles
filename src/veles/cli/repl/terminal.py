"""Terminal-facing leaf helpers for the inline REPL.

The lowest layer of the `cli/repl/` stack: rich `Console` construction,
theme resolution, token/timestamp formatting, the startup banner, the
resume recap, the `/help` table, and the kitty keyboard-protocol
enable/disable sequences. No dependency on any other `cli/repl` module at
module scope — everything above imports FROM here (the base of the import
DAG). The one cross-reference, `_print_resume_recap` → `_render_answer`,
is a function-local import to avoid a terminal↔turn module cycle.
"""

from __future__ import annotations

import datetime as _dt
import sys
import time
from contextlib import contextmanager

from prompt_toolkit.application import run_in_terminal
from prompt_toolkit.patch_stdout import StdoutProxy

# Window inside which a second Ctrl+C at the prompt is treated as exit.
_CTRL_C_EXIT_WINDOW_S = 1.5


# Kitty keyboard protocol (https://sw.kovidgoyal.net/kitty/keyboard-protocol/).
# We push the "disambiguate escape codes" flag on REPL start and pop it on exit;
# capable terminals (kitty, WezTerm, Ghostty, foot, iTerm2 ≥3.5, Alacritty) then
# report Shift+Enter as a DISTINCT sequence — the only reliable way to tell it
# from plain Enter without per-terminal config. Terminals without support ignore
# the enable sequence, so there's no regression.
_KITTY_ENABLE = "\x1b[>1u"  # push flags: disambiguate escape codes
_KITTY_DISABLE = "\x1b[<u"  # pop flags


class _NonBlockingStdoutProxy(StdoutProxy):
    """`StdoutProxy` that runs the terminal write in an executor thread instead
    of on the event loop.

    Confirmed root cause of the REPL "freeze" (HUD timer + spinner stop, Esc goes
    dead) on heavy turns: prompt_toolkit's stock proxy writes via
    `run_in_terminal(..., in_executor=False)`, so the actual `write()` runs on the
    event-loop thread. When a turn streams output faster than the terminal can
    drain it, the OS output buffer fills, `write()` blocks, and the whole loop
    freezes. Running the write `in_executor=True` blocks only a pool thread — the
    loop keeps animating the HUD and stays responsive to Esc/Ctrl+C. Ordering is
    preserved: the base class serialises `_write_and_flush` on its flush thread,
    and `run_in_terminal` queues concurrent requests."""

    def _write_and_flush(self, loop, text: str) -> None:  # type: ignore[override]
        def write_and_flush() -> None:
            self._output.enable_autowrap()
            if self.raw:
                self._output.write_raw(text)
            else:
                self._output.write(text)
            self._output.flush()

        if loop is None:
            write_and_flush()  # no app running — write immediately (pt's fallback)
        else:
            loop.call_soon_threadsafe(
                lambda: run_in_terminal(write_and_flush, in_executor=True)
            )


@contextmanager
def patch_stdout_nonblocking(raw: bool = True):
    """Drop-in for prompt_toolkit's `patch_stdout` using `_NonBlockingStdoutProxy`,
    so heavy streamed output can't block the event loop and freeze the REPL."""
    with _NonBlockingStdoutProxy(raw=raw) as proxy:
        original_stdout, original_stderr = sys.stdout, sys.stderr
        sys.stdout = proxy  # type: ignore[assignment]
        sys.stderr = proxy  # type: ignore[assignment]
        try:
            yield
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr


def _kitty_disable_keyboard() -> None:
    """Pop the kitty keyboard flags. Idempotent and safe on any terminal (the
    sequence is ignored where unsupported). Runs on every REPL exit path plus an
    `atexit` backstop, so a crash never leaves the shell stuck in kitty mode."""
    try:
        if sys.stdout.isatty():
            sys.stdout.write(_KITTY_DISABLE)
            sys.stdout.flush()
    except Exception:
        pass


def _register_kitty_sequences() -> None:
    """Teach prompt_toolkit the kitty-protocol CSI-u sequences so keys keep
    working once we enable the protocol.

    Under "disambiguate escape codes" a capable terminal sends:
      - Shift+Enter → `\\x1b[13;2u`, Alt+Enter → `\\x1b[13;3u` → the spare `F24`
        key, which `_ReplApp` binds to "insert newline" (Enter stays submit).
      - Esc → `\\x1b[27u`, Shift+Tab → `\\x1b[9;2u`, Backspace → `\\x1b[127u`.
      - `Ctrl+<letter>` → `\\x1b[<codepoint>;5u`. These MUST be remapped or the
        protocol would break pt's emacs line-editing (Ctrl+A/E/K/W…) and our
        own Ctrl+C/D/J/O bindings.
    Each maps to the SAME `Keys.*` member as the legacy byte, so mapping both is
    purely additive: whichever form the terminal emits resolves identically, and
    plain text / unmodified Enter/Tab/arrows are untouched. Idempotent."""
    from prompt_toolkit.input import ansi_escape_sequences as _aes
    from prompt_toolkit.keys import Keys

    seqs = _aes.ANSI_SEQUENCES
    # Shift+Enter / Alt+Enter / xterm modifyOtherKeys → newline.
    for seq in ("\x1b[27;2;13~", "\x1b[13;2u", "\x1b[13;3u"):
        seqs[seq] = Keys.F24
    # Unmodified specials, in case a terminal reports them as CSI-u as well.
    seqs["\x1b[13u"] = Keys.ControlM  # Enter → submit
    seqs["\x1b[9u"] = Keys.ControlI  # Tab
    seqs["\x1b[27u"] = Keys.Escape
    seqs["\x1b[127u"] = Keys.Backspace
    seqs["\x1b[9;2u"] = Keys.BackTab  # Shift+Tab → cycle mode
    seqs["\x1b[127;5u"] = Keys.Backspace  # Ctrl+Backspace
    # Ctrl+a..z → Keys.ControlA..ControlZ (same enum as legacy \x01..\x1a).
    for i in range(26):
        seqs[f"\x1b[{ord('a') + i};5u"] = getattr(Keys, f"Control{chr(ord('A') + i)}")
    # JCUKEN (Russian) layout: under the kitty protocol `Ctrl+<letter>` reports
    # the Cyrillic codepoint, not the Latin one — e.g. Ctrl+C on a Russian
    # keyboard sends the letter "es" (U+0441 = 1089) as `\x1b[1089;5u`, which the
    # Latin loop above doesn't cover, so pt prints the raw sequence into the input
    # instead of interrupting. Map each Cyrillic letter to the SAME control key as
    # the Latin letter on its physical key (QWERTY position), for both cases.
    _qwerty = "qwertyuiopasdfghjklzxcvbnm"
    _jcuken = "йцукенгшщзфывапролдячсмить"  # physical-key order over _qwerty
    for latin, cyr in zip(_qwerty, _jcuken, strict=True):
        ctrl = getattr(Keys, f"Control{latin.upper()}")
        for ch in (cyr, cyr.upper()):
            seqs[f"\x1b[{ord(ch)};5u"] = ctrl


def _console():
    from rich.console import Console

    # force_terminal so theme colours survive through prompt_toolkit's
    # patch_stdout proxy (which doesn't report as a tty). Console has no cached
    # file, so it writes to the *current* sys.stdout — i.e. the proxy while the
    # Application runs, so background/streamed output lands above the input box.
    return Console(force_terminal=True)


def _fmt_ts(ts: float) -> str:
    return _dt.datetime.fromtimestamp(ts, tz=_dt.UTC).astimezone().strftime("%Y-%m-%d %H:%M")


def _resolve_theme(state):
    """The active TUI theme (user config → fallback), reused for the REPL's
    colours so `veles repl` matches the user's installed theme."""
    from veles.cli.tui_theme import THEMES, load_theme

    return load_theme(getattr(state, "theme_name", "") or "everforest") or THEMES["everforest"]


def _fmt_tok(n: int) -> str:
    if n < 1_000:
        return str(n)
    if n < 1_000_000:
        return f"{n // 1_000}k"
    return f"{n // 1_000_000}M"


def _tool_row(rec: dict[str, object]) -> str:
    """One line of the inspector's expanded activity view: a
    running/done/failed marker, the tool label, and its elapsed duration.
    `rec` is a `_ReplApp.tool_activity` entry — `end` is None while running,
    so the duration ticks live off the HUD's 0.3s redraw."""
    status = rec["status"]
    start = float(rec["start"])  # type: ignore[arg-type]
    end = rec["end"]
    duration = (float(end) if end is not None else time.monotonic()) - start  # type: ignore[arg-type]
    marker = {"running": "⏳", "done": "✓", "failed": "✗"}.get(str(status), "⚒")
    return f"{marker} {rec['name']} ({duration:.1f}s)"


def _settled_status(state) -> str:
    """The quiet bottom bar of the inline app: current mode + settled token /
    cache stats ONLY. It changes after a turn completes (never mid-generation),
    so it stays still while the answer streams; the live "working…" HUD with the
    per-request counters lives in the generation body instead. Provider/model,
    session id and insights are deliberately dropped here (they're in the
    startup banner and `/status`) — the bar is meant to be quiet."""
    from veles.core.model_windows import context_window_for

    parts = [f"[{state.mode}]"]
    if state.tokens_in or state.tokens_out:
        parts.append(f"tok {_fmt_tok(state.tokens_in)}/{_fmt_tok(state.tokens_out)}")
    occupied = state.last_prompt_tokens or state.last_turn_total_tokens
    if occupied:
        limit = context_window_for(state.model)
        pct = round(occupied / limit * 100) if limit else 0
        parts.append(f"ctx {_fmt_tok(occupied)}/{_fmt_tok(limit)} ({pct}%)")
    if state.last_turn_cache_read:
        parts.append(f"cache {_fmt_tok(state.last_turn_cache_read)}")
    return " · ".join(parts)


def _banner(console, provider: str, model: str, mode: str, theme) -> None:
    from rich.panel import Panel
    from rich.text import Text

    body = Text()
    body.append("veles", style=f"bold {theme.accent}")
    body.append("  ·  ")
    body.append(f"{provider}:{model}", style=theme.success)
    body.append("  ·  ")
    body.append(f"mode {mode}", style=theme.accent)
    body.append("\n")
    body.append("/help for commands · Shift+Tab cycles mode · Ctrl+D to exit", style=theme.muted)
    console.print(Panel(body, expand=False, border_style=theme.border, padding=(0, 2)))


def _print_resume_recap(console, theme, store, session_id: str, *, max_msgs: int = 4) -> None:
    """On `-c`/`--resume`, replay the tail of the resumed conversation so the
    user SEES they're continuing it (the agent already has the full history via
    session_id; this is just the visible recap). Best-effort."""
    from veles.cli.commands.repl import _render_answer

    try:
        msgs = store.load_messages(session_id)
    except Exception:
        return
    convo = [m for m in msgs if m.role in ("user", "assistant") and (m.content or "").strip()]
    if not convo:
        return
    console.print(
        f"  [dim]— continuing this conversation ({len(convo)} messages); recent context: —[/dim]\n"
    )
    for m in convo[-max_msgs:]:
        body = (m.content or "").strip()
        if len(body) > 600:
            body = body[:600].rstrip() + " […]"
        if m.role == "user":
            console.print(f"❯ {body}", style=f"bold {theme.accent}", markup=False)
        else:
            _render_answer(console, body)
    console.print()


def _print_repl_help(console) -> None:
    from rich.table import Table

    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(style="cyan", no_wrap=True)
    t.add_column(style="white")
    rows = [
        ("/help", "show this help"),
        ("/mode [name]", "show/set mode (auto·planning·writing·goal); Shift+Tab cycles"),
        ("/model [id]", "show or set the active model"),
        ("/theme [name]", "show or set the active TUI theme"),
        ("/sessions", "list recent sessions and resume one"),
        ("/history [N]", "list recent sessions"),
        ("/tokens · /context", "token totals · context vs model window"),
        ("/status", "model/mode/session/provider snapshot"),
        ("/save <slug>", "save the last answer to the wiki"),
        ("/insights · /rules", "recent learned insights / behavioural rules"),
        ("/errors", "show errors from this REPL session"),
        ("/clear", "start a fresh session"),
        ("/quit", "exit (or Ctrl+D)"),
    ]
    for cmd, desc in rows:
        t.add_row(cmd, desc)
    console.print(t)
    console.print(
        "  [dim]@ file picker · Ctrl+I/Ctrl+O inspector · Ctrl+X Ctrl+E $EDITOR · "
        "Ctrl+V paste image · Shift+Tab cycle mode[/dim]"
    )
    console.print(
        "  [dim]copy: select with the mouse and press ⌘C (macOS) / Ctrl+Shift+C (Linux) — "
        "native terminal copy.[/dim]\n"
    )
