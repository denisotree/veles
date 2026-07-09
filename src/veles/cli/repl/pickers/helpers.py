"""Stateless picker helpers shared by the inline REPL's pickers.

Case-insensitive filters for the model / `@`-file pickers, the `@`
trigger-boundary rule, the paste-filename scheme, and the fallback
(simple-loop) model/theme listers + inline session picker. No `_ReplApp`
state here — these are pure functions the picker mixins and the simple
loop both call. Imports only from `terminal` (the base leaf).
"""

from __future__ import annotations

import time

from veles.cli.repl.terminal import _fmt_ts


def _filter_models(models, text: str) -> list[str]:
    """Case-insensitive substring filter for the model picker — the same
    helper backs the inline app picker and could back the fallback list."""
    f = text.strip().lower()
    if not f:
        return list(models)
    return [m for m in models if f in m.lower()]


def _filter_files(paths: list[str], text: str) -> list[str]:
    """Case-insensitive substring filter for the `@` file picker — same shape
    as `_filter_models`, kept as a separate name for clarity/searchability."""
    return _filter_models(paths, text)


def _at_trigger_boundary(text_before_cursor: str) -> bool:
    """True when a freshly-typed `@` at this cursor position should open the
    file picker: start of input, or right after whitespace/newline. Mirrors
    the old Textual `Composer` rule — `foo@bar.com` must NOT trigger it since
    the `@` lands mid-word."""
    return not text_before_cursor or text_before_cursor[-1].isspace()


def _new_paste_filename() -> str:
    """Timestamp + short hash, e.g. `20260704-153000-a1b2c3d4.png` — same
    naming scheme the old Textual composer used for Ctrl+V image pastes."""
    import hashlib

    ts = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    sha = hashlib.sha1(str(time.time_ns()).encode()).hexdigest()[:8]
    return f"{ts}-{sha}.png"


def _print_model_list(console, provider: str, current: str, *, refresh: bool = False) -> None:
    """Fallback (simple-loop) model lister: fetch the provider's catalogue and
    print it, marking the current model. No interactive picker here — the
    default REPL (inline Application) has the filterable picker; the fallback
    just shows the list and relies on `/model <id>` to set one."""
    from veles.cli.repl.model_fetcher import fetch_models

    try:
        result = fetch_models(provider, refresh=refresh)
    except Exception as exc:
        console.print(f"  could not fetch models: {exc}", style="red", markup=False)
        return
    if not result.models:
        console.print(
            "  no models (no API key / provider offline) — set with /model <id>",
            style="yellow",
            markup=False,
        )
        return
    console.print(
        f"  {provider} · {len(result.models)} models · {result.source}",
        style="cyan",
        markup=False,
    )
    for m in result.models[:40]:
        console.print(f"    {m}{'  ← current' if m == current else ''}", style="dim", markup=False)
    if len(result.models) > 40:
        console.print(f"    … +{len(result.models) - 40} more", style="dim", markup=False)
    console.print("  set with /model <id>", style="dim", markup=False)


def _print_theme_list(console, current: str) -> None:
    """Fallback (simple-loop) theme lister, mirroring `_print_model_list`: the
    inline Application has the filterable `/theme` picker; the fallback just
    shows the list and relies on `/theme <name>` to set one."""
    from veles.cli.tui_theme import list_themes

    names = list_themes()
    if not names:
        console.print("  no themes found", style="yellow", markup=False)
        return
    console.print(f"  {len(names)} themes", style="cyan", markup=False)
    for name in names:
        marker = "  ← current" if name == current else ""
        console.print(f"    {name}{marker}", style="dim", markup=False)
    console.print("  set with /theme <name>", style="dim", markup=False)


def _pick_session(store, state, console) -> None:
    """Inline session picker: a rich table of recent sessions + a numbered
    prompt to resume one. Stays in the normal buffer (no alt screen)."""
    from rich.prompt import Prompt
    from rich.table import Table

    sessions = store.list_sessions(limit=15)
    if not sessions:
        console.print("  [dim]no sessions yet[/dim]")
        return
    table = Table(box=None, padding=(0, 2), header_style="bold cyan")
    table.add_column("#", justify="right")
    table.add_column("id")
    table.add_column("last activity")
    table.add_column("turns", justify="right")
    table.add_column("title")
    for i, s in enumerate(sessions, 1):
        marker = "[green]●[/green]" if s.id == state.session_id else " "
        table.add_row(
            f"{marker}{i}",
            s.id[:8],
            _fmt_ts(s.last_activity_at),
            str(s.turn_count),
            s.title or "[dim](untitled)[/dim]",
        )
    console.print(table)
    choice = Prompt.ask("  resume # (blank to cancel)", default="", show_default=False)
    choice = choice.strip()
    if choice.isdigit() and 1 <= int(choice) <= len(sessions):
        picked = sessions[int(choice) - 1]
        state.session_id = picked.id
        console.print(f"  [green]resumed[/green] {picked.id}")
