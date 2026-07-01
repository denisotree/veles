"""`veles repl` — inline streaming REPL (the "act like `cat`" interface).

Why this exists (research in M185): the full-screen `veles tui` runs in the
terminal's *alternate screen buffer* and must capture the mouse to scroll,
which disables the terminal's native text selection and makes the terminal
eat ⌘C. There is no way to have app-managed wheel-scroll AND native
selection/copy at once in a full-screen TUI.

This REPL renders to the **normal** screen buffer and never enables mouse
reporting, so the terminal owns scrollback, text selection and clipboard
copy (⌘C on macOS / Ctrl+Shift+C on Linux) natively. Assistant output
streams straight to stdout; the input line is drawn inline by prompt_toolkit
(no alternate screen, no mouse capture). Visual polish is `rich`.

It reuses the framework-agnostic core the Textual TUI already exposes —
`AppState`, the `slash` command registry, and the `core.modes` FSM
(auto/planning/writing/goal). Only the presentation layer changes: the
Textual app + bridge + widgets become print-based callbacks.
"""

from __future__ import annotations

import argparse
import asyncio
import contextvars
import datetime as _dt
import os
import sys
import time
from collections import deque

from veles.core.project import Project

# Window inside which a second Ctrl+C at the prompt is treated as exit.
_CTRL_C_EXIT_WINDOW_S = 1.5

# The rich.Live pinning the status bar during the active turn (or None). The
# ask_user picker runs a prompt_toolkit Application mid-turn, which needs the
# terminal — `_suspend_live` pauses this Live around it. Single-threaded loop,
# so a module global is safe.
_ACTIVE_LIVE = None


def _suspend_live():
    """Context manager that pauses the active status-bar Live so a nested
    interactive prompt (the ask_user picker) can own the terminal, then resumes."""
    import contextlib

    @contextlib.contextmanager
    def _cm():
        live = _ACTIVE_LIVE
        if live is not None:
            live.stop()
        try:
            yield
        finally:
            if live is not None:
                live.start(refresh=True)

    return _cm()


# Injected into the REPL's system prompt for normal auto/writing turns (NOT
# goal mode, which drives its own one-step-per-turn phase prompts). Two levers:
# persistence — the biggest reason a small model "gives up" after one or two
# edits is that nothing tells it to finish the whole job — and routing genuine
# decisions through the interactive `ask_user` picker instead of prose.
_REPL_BEHAVIOUR_BLOCK = (
    "## Working through a task\n"
    "When the user asks you to carry out work — especially across MANY items "
    '("loop through all pages", "fix everything", "review each file") — do the '
    "WHOLE task in this turn. Work item by item: read it, make the change, move "
    "to the next, until every item is handled. You have many tool calls per turn "
    "— use them. Do NOT stop after one or two items to summarise and ask whether "
    "to continue; that needlessly interrupts the work. Stop only when the task "
    "is genuinely complete or you hit a real blocker.\n\n"
    "## Asking the user\n"
    "Pause to ask ONLY for a real decision the user must make — a choice between "
    "concrete alternatives, or confirmation of a risky / irreversible action. "
    "When you do, call the `ask_user` tool with `options=[...]` (it renders an "
    "arrow-key picker) instead of writing the question as prose, e.g. "
    '`ask_user("Apply the plan or exclude sources/?", options=["Apply fully", '
    '"Exclude sources/", "Cancel"])`. Never end a turn with a plain-text choice '
    "or yes/no question, and never ask permission for routine steps of a task "
    "you were already told to do — just do them."
)


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


def _print_repl_help(console) -> None:
    from rich.table import Table

    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(style="cyan", no_wrap=True)
    t.add_column(style="white")
    rows = [
        ("/help", "show this help"),
        ("/mode [name]", "show/set mode (auto·planning·writing·goal); Shift+Tab cycles"),
        ("/model [id]", "show or set the active model"),
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
        "  [dim]copy: select with the mouse and press ⌘C (macOS) / Ctrl+Shift+C (Linux) — "
        "native terminal copy.[/dim]\n"
    )


def _build_runtime(args: argparse.Namespace, project: Project):
    """Resolve provider/model, gate the API key, and build the per-turn Agent
    factory + AppState + store — a faithful mirror of `tui.run_tui`'s setup.

    Returns ``(state, factory, store)`` or ``None`` when the key gate fails.

    NOTE (dedup): intentionally duplicates `run_tui`'s factory for now. Once
    the REPL is canonical, both should share one builder.
    """
    from veles.cli import (
        _PLANNING_TOOLS,
        _PROVIDER_API_KEY_ENVS,
        _RUN_TOOLS,
        _build_compressor,
        _build_run_system_prompt,
        _ensure_api_key,
        _load_skills,
        _make_provider,
        _touch_active_project,
        _warn_if_agents_md_invalid,
    )
    from veles.core.agent import Agent
    from veles.core.memory import SessionStore
    from veles.core.model_resolver import (
        ConfigurationError,
        ensure_model_configured,
        resolve_effective_model,
        resolve_effective_provider,
    )
    from veles.core.model_windows import default_hard_ceiling_for
    from veles.core.modes import get_mode
    from veles.tui.state import AppState

    args.provider = resolve_effective_provider(args, project)
    try:
        args.model = ensure_model_configured(resolve_effective_model(args, project))
    except ConfigurationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return None
    if args.provider in _PROVIDER_API_KEY_ENVS and not _ensure_api_key(args.provider):
        return None
    _touch_active_project(project)
    _warn_if_agents_md_invalid(project)

    provider = _make_provider(args.provider)
    compressor = _build_compressor(args, project, provider)
    registries = {
        "writing": _load_skills(project, _RUN_TOOLS, provider=provider, model=args.model),
        "planning": _load_skills(project, _PLANNING_TOOLS, provider=provider, model=args.model),
    }
    store = SessionStore(project.memory_db_path)

    def factory(state, *, mode_override=None, extra_system=None):
        active = mode_override or state.mode
        mode = get_mode(active)
        is_planning = active == "planning"
        registry_key = "planning" if is_planning else "writing"
        # M186: rebuild the system prompt EVERY turn (not only when the session
        # is fresh), so the *current* mode's block reaches the model. Agent's
        # `_bootstrap_history` refreshes history[0] with a passed system prompt
        # on resume. Without this, the strict PLANNING block baked on a first
        # planning turn stays frozen for the whole session and the model keeps
        # insisting it can't execute even after the turn routed to writing.
        sys_chunks: list[str] = []
        base = _build_run_system_prompt(args, project)
        if base:
            sys_chunks.append(base)
        if mode.system_block.strip():
            sys_chunks.append(mode.system_block.strip())
        if extra_system and extra_system.strip():
            # A phase prompt is driving this turn (goal mode's own FSM, which is
            # deliberately one-step-per-turn) — don't inject the persistence
            # block, it would contradict "run the step, then STOP".
            sys_chunks.append(extra_system.strip())
        else:
            sys_chunks.append(_REPL_BEHAVIOUR_BLOCK)
        system_prompt = "\n\n".join(sys_chunks) if sys_chunks else None
        return Agent(
            provider=provider,
            registry=registries[registry_key],
            model=state.model,
            max_iterations=args.max_iterations,
            system_prompt=system_prompt,
            verbose=getattr(args, "verbose", False),
            store=store,
            session_id=state.session_id,
            compressor=compressor,
            hard_ceiling_tokens=default_hard_ceiling_for(state.model),
            plan_mode=is_planning,
        )

    from veles.core.user_config import load_user_config

    user_cfg = load_user_config()
    state = AppState(
        session_id=getattr(args, "resume", None),
        provider_name=args.provider,
        model=args.model,
        theme_name=(user_cfg.tui_theme if user_cfg and user_cfg.tui_theme else "everforest"),
    )
    return state, factory, store


def _make_turn_callbacks(console, theme, errors: list[str], on_meta=None):
    """Build (post, on_text, on_event) for a `ModeContext`, plus a holder for
    the final `RunResult`.

    These **stream by block**: answer tokens accumulate in a buffer, and each
    completed Markdown block (paragraph, list, table, fenced code) is rendered
    formatted as soon as its terminating blank line arrives — progressive AND
    formatted. `flush()` renders the trailing block at end of turn. Under the
    Application's `patch_stdout`, writes from the executor thread appear above
    the live input box.

    `on_meta(kind, text)` (optional) is the live-generation HUD sink: it
    receives ``("stream", chunk)`` for every answer chunk (so the app can show a
    running token estimate), ``("mode", text)`` on a mode switch, and
    ``("tool", text)`` on each tool call. When it's None (the fallback simple
    loop) mode switches print inline instead.

    Returns ``(post, on_text, on_event, holder, flush)``.
    """
    from veles.tui.messages import AgentError, ChatDelta, SystemLine, TurnDone

    holder: dict[str, object] = {}
    buf = [""]  # mutable string cell shared across chunks

    def _emit(chunk: str) -> None:
        if on_meta is not None:
            on_meta("stream", chunk)
        buf[0] += chunk
        blocks, buf[0] = _split_blocks(buf[0])
        for block in blocks:
            if block.strip():
                _render_answer(console, block)

    def flush() -> None:
        if buf[0].strip():
            _render_answer(console, buf[0])
        buf[0] = ""

    def post(msg) -> None:
        if isinstance(msg, TurnDone):
            holder["result"] = msg.result
        elif isinstance(msg, SystemLine):
            # A mode switch etc. — into the live meta HUD, or inline as a dim
            # line when there's no HUD (fallback loop).
            if on_meta is not None:
                on_meta("mode", msg.text)
            else:
                console.print(f"  ⋅ {msg.text}", style=theme.muted, markup=False)
        elif isinstance(msg, ChatDelta):
            _emit(msg.text)
        elif isinstance(msg, AgentError):
            errors.append(str(msg.exc))
            console.print(f"\nerror: {msg.exc}", style=theme.error, markup=False)

    def on_text(text: str) -> None:
        _emit(text)

    def on_event(event) -> None:
        if getattr(event, "type", "") != "tool_call":
            return
        name = getattr(event, "name", "")
        args = getattr(event, "arguments", {}) or {}
        if on_meta is not None:
            label = f"{name} {args.get('path', '')}".strip()
            on_meta("tool", label)
        # Preview file edits as a coloured diff, in order with the answer text.
        if name in ("edit_file", "write_file"):
            flush()  # render any pending answer text first, so ordering holds
            _render_edit_diff(console, theme, name, args)

    return post, on_text, on_event, holder, flush


def _render_answer(console, text: str) -> None:
    """Pretty-print a Markdown block — headings, lists, tables, links,
    bold/italic, and syntax-highlighted code blocks. Falls back to plain text
    if rendering ever raises so a glitch never eats the answer."""
    from rich.markdown import Markdown

    try:
        console.print(Markdown(text))
    except Exception:
        console.print(text, markup=False)


def _render_edit_diff(console, theme, name: str, arguments: dict) -> None:
    """Show a coloured unified diff (red = removed, green = added) for a file
    edit, in a code block. `edit_file` diffs its old_string → new_string;
    `write_file` diffs the file's current content → the new content (read before
    the write lands, since the tool-call event fires ahead of execution)."""
    import difflib

    from rich.syntax import Syntax

    path = str(arguments.get("path", "?"))
    if name == "edit_file":
        old = str(arguments.get("old_string", ""))
        new = str(arguments.get("new_string", ""))
    else:  # write_file
        new = str(arguments.get("content", ""))
        old = ""
        try:
            from veles.core.path_guard import resolve_safe

            p = resolve_safe(path)
            if p.is_file():
                old = p.read_text(encoding="utf-8")
        except Exception:
            old = ""

    diff = "\n".join(
        difflib.unified_diff(
            old.splitlines(),
            new.splitlines(),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
    )
    if not diff.strip():
        return
    console.print(f"  ✎ {path}", style=theme.accent, markup=False)
    console.print(Syntax(diff, "diff", background_color="default", word_wrap=True))


def _split_blocks(buf: str) -> tuple[list[str], str]:
    """Split a growing Markdown buffer into (complete_blocks, remainder).

    Blocks are separated by blank lines OUTSIDE fenced code (``` / ~~~). The
    trailing incomplete block — everything after the last blank-line boundary,
    an unterminated code fence, or a partial final line — is the remainder,
    kept buffered until more tokens arrive. This lets the REPL render each
    finished block (paragraph, list, table, code fence) as it completes,
    streaming *and* formatted."""
    lines = buf.split("\n")
    tail = lines.pop()  # text after the final "\n" — a partial line (or "")
    blocks: list[str] = []
    cur: list[str] = []
    in_fence = False
    for line in lines:
        s = line.lstrip()
        if s.startswith("```") or s.startswith("~~~"):
            in_fence = not in_fence
            cur.append(line)
        elif line.strip() == "" and not in_fence:
            if cur:
                blocks.append("\n".join(cur))
                cur = []
            # else: swallow extra blank separators
        else:
            cur.append(line)
    remainder = "\n".join([*cur, tail]) if cur else tail
    return blocks, remainder


def _update_state_after_turn(state, result) -> None:
    """Carry session id, last reply and token totals forward."""
    if result is None:
        return
    if result.session_id:
        state.session_id = result.session_id
    if result.text:
        state.last_assistant_text = result.text
    usage = getattr(result, "usage", None)
    if usage is not None:
        state.tokens_in += getattr(usage, "prompt_tokens", 0) or 0
        state.tokens_out += getattr(usage, "completion_tokens", 0) or 0
        state.last_turn_total_tokens = getattr(usage, "total_tokens", 0) or 0
        # Mirror the TUI (app.py): context occupancy = last request's prompt
        # size; cache-read tokens drive the `cache` chip (M177/M178).
        state.last_prompt_tokens = (
            getattr(usage, "last_prompt_tokens", 0)
            or getattr(usage, "prompt_tokens", 0)
            or getattr(usage, "total_tokens", 0)
        )
        state.last_turn_cache_read = getattr(usage, "cache_read_tokens", 0)


def _run_mode_turn(state, project, factory, line: str, console, errors: list[str], theme):
    """Drive one user turn through the active mode's FSM (fallback simple loop).
    The answer streams block-by-block straight to stdout; the settled status bar
    is the prompt's bottom-toolbar between turns. No pinned-during-generation bar
    here — rich.Live can't pin over output taller than the screen without
    stranding content, so that job belongs to the inline Application (default)."""
    from veles.core.modes import ModeContext, get_mode

    post, on_text, on_event, holder, flush = _make_turn_callbacks(console, theme, errors)
    ctx = ModeContext(
        state=state,
        project=project,
        factory=factory,
        post=post,
        on_text=on_text,
        on_event=on_event,
    )
    try:
        get_mode(state.mode).run_turn(line, ctx)
    except KeyboardInterrupt:
        console.print("\n  ⋅ interrupted", style=theme.muted, markup=False)
    finally:
        flush()  # render the trailing block
    console.print()  # spacing after the answer
    return holder.get("result")


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


def _handle_slash(
    line: str, registry, state, project, store, console, errors: list[str]
) -> tuple[bool, str | None]:
    """Dispatch a `/command`. Returns ``(should_quit, submit_prompt)``."""
    from veles.tui.slash import SlashContext

    cmd = line.split()[0].lower()
    # REPL-local commands that the shared (Textual) registry doesn't own.
    if cmd in ("/help", "/h"):
        _print_repl_help(console)
        return False, None
    if cmd == "/errors":
        if not errors:
            console.print("  [dim]no errors this session[/dim]")
        else:
            for e in errors[-20:]:
                console.print(f"  [red]·[/red] {e}")
        return False, None
    if cmd == "/sessions":
        _pick_session(store, state, console)
        return False, None
    if cmd == "/resume":
        parts = line.split(maxsplit=1)
        arg = parts[1].strip() if len(parts) > 1 else ""
        match = (
            next((s for s in store.list_sessions(limit=50) if s.id.startswith(arg)), None)
            if arg
            else None
        )
        if match is not None:
            state.session_id = match.id
            console.print(f"  resumed {match.id}", style="green")
        else:
            console.print("  /resume <id-prefix> — see /sessions for ids", style="yellow")
        return False, None

    ctx = SlashContext(state=state, project=project, store=store)
    result = registry.dispatch(line, ctx)
    if result is None:
        console.print(f"  [red]unknown command:[/red] {cmd} (try /help)")
        return False, None
    if result.text:
        # markup=False: handler text is plain and may contain literal brackets.
        console.print(result.text, style="red" if result.is_error else None, markup=False)
    if result.clear_chat:
        # Fresh session; never wipe the terminal (keep the scrollback the whole
        # inline model exists to preserve).
        state.session_id = None
        state.last_assistant_text = None
    if result.open_picker == "sessions":
        _pick_session(store, state, console)
    elif result.open_picker:
        console.print(f"  [dim]{result.open_picker}: set directly, e.g. /model <id>[/dim]")
    return result.quit, result.submit_prompt


def _make_prompt_session(project: Project, registry, state):
    """prompt_toolkit session: history under `.veles/`, slash autocompletion,
    a status bottom-toolbar, Shift+Tab to cycle mode. Plain prompt mode — no
    alternate screen, no mouse capture."""
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.key_binding import KeyBindings

    from veles.core.modes import next_mode

    extra = ("/sessions", "/errors")

    class _SlashCompleter(Completer):
        def get_completions(self, document, complete_event):
            text = document.text_before_cursor
            if not text.startswith("/") or " " in text:
                return
            for name in [*registry.names(), *extra]:
                if name.startswith(text):
                    yield Completion(name, start_position=-len(text))

    def _toolbar():
        return f" {_settled_status(state)} · Shift+Tab mode · /help · Ctrl+D exit "

    kb = KeyBindings()

    @kb.add("s-tab")
    def _(event) -> None:
        state.mode = next_mode(state.mode)  # type: ignore[assignment]
        event.app.invalidate()

    hist_path = project.state_dir / "repl_history"
    return PromptSession(
        history=FileHistory(str(hist_path)),
        completer=_SlashCompleter(),
        complete_while_typing=True,
        key_bindings=kb,
        bottom_toolbar=_toolbar,
    )


def _choice_picker(theme, question: str, options: list[str]):
    """Inline arrow-key picker (normal screen buffer, no mouse) for a choice
    question. Lists the options plus a final free-text entry; returns the chosen
    option string, a typed free-text answer, or None on Esc/no-TTY. Mirrors the
    trust-ladder menu pattern."""
    from prompt_toolkit import Application
    from prompt_toolkit.formatted_text import FormattedText
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout, Window
    from prompt_toolkit.layout.controls import FormattedTextControl

    free_label = "✎ свой вариант…"
    items = [*options, free_label]
    sel = [0]
    picked: list[int | None] = [None]
    kb = KeyBindings()

    @kb.add("up")
    def _u(e) -> None:
        sel[0] = (sel[0] - 1) % len(items)

    @kb.add("down")
    def _d(e) -> None:
        sel[0] = (sel[0] + 1) % len(items)

    for _i in range(min(9, len(items))):

        @kb.add(str(_i + 1))
        def _n(e, idx=_i) -> None:
            sel[0] = idx

    @kb.add("enter")
    def _en(e) -> None:
        picked[0] = sel[0]
        e.app.exit()

    @kb.add("escape")
    @kb.add("c-c")
    def _es(e) -> None:
        picked[0] = None
        e.app.exit()

    def _text():
        lines: list[tuple[str, str]] = [("bold", f"{question}\n\n")]
        for i, label in enumerate(items):
            style = f"bold {theme.accent}" if i == sel[0] else ""
            marker = "❯" if i == sel[0] else " "
            lines.append((style, f"  {marker} {label}\n"))
        lines.append(("ansibrightblack", "\n  ↑↓ выбор · Enter · Esc отмена\n"))
        return FormattedText(lines)

    Application(
        layout=Layout(Window(FormattedTextControl(_text, focusable=True))),
        key_bindings=kb,
        full_screen=False,
        mouse_support=False,
    ).run()

    idx = picked[0]
    if idx is None:
        return None
    if idx == len(items) - 1:  # free-text entry
        return _free_text(theme)
    return options[idx]


def _free_text(theme):
    from prompt_toolkit import prompt

    try:
        answer = prompt(_pt_html(theme, "  ваш вариант ❯ ")).strip()
    except (EOFError, KeyboardInterrupt):
        return None
    return answer or None


def _pt_html(theme, text: str):
    from prompt_toolkit.formatted_text import HTML

    return HTML(f'<style fg="{theme.accent}">{text}</style>')


def _ask_repl(console, theme, question: str, options: list[str] | None):
    """Question prompter for the REPL: an interactive picker when the agent
    offers options, a free-text line otherwise. Returns None when there's no
    interactive TTY so the agent proceeds on its best assumption."""
    if not sys.stdin.isatty():
        return None
    # A turn's status-bar Live (if any) owns the terminal — pause it so the
    # picker's prompt_toolkit Application can take over, then resume.
    with _suspend_live():
        if options:
            return _choice_picker(theme, question, options)
        console.print(f"\n[agent] {question}", style=theme.accent, markup=False)
        return _free_text(theme)


def _run_simple_repl(
    args, project, state, factory, store, registry, console, theme, errors
) -> None:
    """Fallback loop on the blocking `PromptSession.prompt()` (set
    `VELES_REPL_SIMPLE=1`). No live-during-generation input; kept as a safety
    net for terminals where the inline Application misbehaves."""
    from prompt_toolkit.formatted_text import HTML

    from veles.core.user_prompt import reset_question_prompter, set_question_prompter

    prompt_html = HTML(f'<style fg="{theme.accent}"><b>❯</b></style> ')
    prompt_session = _make_prompt_session(project, registry, state)
    # Route agent `ask_user` questions to an inline picker / free-text prompt.
    qtoken = set_question_prompter(lambda q, opts=None: _ask_repl(console, theme, q, opts))
    console.rule(style=theme.border, characters="─")
    try:
        _simple_repl_loop(
            args,
            project,
            state,
            factory,
            store,
            registry,
            console,
            theme,
            errors,
            prompt_session,
            prompt_html,
        )
    finally:
        reset_question_prompter(qtoken)


def _simple_repl_loop(
    args,
    project,
    state,
    factory,
    store,
    registry,
    console,
    theme,
    errors,
    prompt_session,
    prompt_html,
) -> None:
    last_ctrl_c = 0.0
    while True:
        try:
            line = prompt_session.prompt(prompt_html)
        except KeyboardInterrupt:
            now = time.monotonic()
            if now - last_ctrl_c <= _CTRL_C_EXIT_WINDOW_S:
                break
            last_ctrl_c = now
            console.print("(press Ctrl+C again or Ctrl+D to exit)", style=theme.muted)
            continue
        except EOFError:
            break
        line = line.strip()
        if not line:
            continue
        if line.startswith("/"):
            should_quit, submit = _handle_slash(
                line, registry, state, project, store, console, errors
            )
            if should_quit:
                break
            if not submit:
                continue
            line = submit
        console.print()
        try:
            result = _run_mode_turn(state, project, factory, line, console, errors, theme)
        except Exception as exc:
            errors.append(str(exc))
            console.print(f"error: {exc}", style=theme.error, markup=False)
            console.rule(style=theme.border, characters="─")
            continue
        _update_state_after_turn(state, result)
        console.rule(style=theme.border, characters="─")


class _ReplApp:
    """Inline prompt_toolkit Application (no alt-screen). A bordered input box
    stays live while a turn runs in a background executor; input typed during
    generation is queued and drained on completion. Output renders ABOVE the
    box via `run_in_terminal`, landing in the terminal's own scrollback — so
    native scroll / selection / copy are preserved.
    """

    # The final picker item — selecting it switches to free-text entry.
    _FREE_LABEL = "✎ свой вариант…"

    def __init__(self, args, project, state, factory, store, registry, console, theme, errors):
        from prompt_toolkit.application import Application
        from prompt_toolkit.completion import Completer, Completion
        from prompt_toolkit.filters import Condition
        from prompt_toolkit.formatted_text import FormattedText
        from prompt_toolkit.history import FileHistory
        from prompt_toolkit.layout import ConditionalContainer, HSplit, Layout, Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.layout.dimension import Dimension
        from prompt_toolkit.styles import Style
        from prompt_toolkit.widgets import Frame, TextArea

        from veles.core.modes import next_mode

        self.args = args
        self.project = project
        self.state = state
        self.factory = factory
        self.store = store
        self.registry = registry
        self.console = console
        self.theme = theme
        self.errors = errors
        self.busy = False
        self.queue: deque[str] = deque()
        self.cancel_token = None
        self._last_ctrl_c = 0.0
        self._next_mode = next_mode
        self._tasks: set = set()  # keep strong refs so tasks aren't GC'd mid-flight
        # --- live-generation meta HUD state (reset per turn) ---
        self.meta_events: list[tuple[str, str]] = []  # ("mode"|"tool", text)
        self.meta_expanded = False
        self.stream_chars = 0
        self.turn_start = 0.0
        self._tick = 0
        # --- mid-turn ask_user picker state (answered inside THIS app; a nested
        # prompt_toolkit Application can't run under the live loop) ---
        self.q_active = False
        self.q_free = False
        self.q_question = ""
        self.q_options: list[str] = []
        self.q_sel = 0
        self.q_answer: str | None = None
        self.q_event = None
        # Capture the caller's ContextVars NOW (constructed inside the CLI's
        # `set_active_project` scope) so background turns can re-enter them —
        # `run_in_executor` does not copy context, and without the active
        # project the tools resolve wrong paths (run_shell cwd → ~/.veles/skills).
        self._parent_ctx = contextvars.copy_context()

        extra = ("/sessions", "/errors", "/resume")

        class _SlashCompleter(Completer):
            def get_completions(self, document, complete_event):
                text = document.text_before_cursor
                if not text.startswith("/") or " " in text:
                    return
                for name in [*registry.names(), *extra]:
                    if name.startswith(text):
                        yield Completion(name, start_position=-len(text))

        self.input = TextArea(
            prompt=FormattedText([("class:prompt", "❯ ")]),
            multiline=True,
            wrap_lines=True,
            height=Dimension(min=1, max=10),
            completer=_SlashCompleter(),
            complete_while_typing=True,
            history=FileHistory(str(project.state_dir / "repl_history")),
            style="class:input",
        )
        frame = Frame(self.input)
        # Live "working…" HUD — visible only while a turn runs and no question is
        # pending. dont_extend_height so it's one line collapsed, a few expanded.
        meta = ConditionalContainer(
            Window(
                FormattedTextControl(self._meta_fragments),
                dont_extend_height=True,
                style="class:meta",
            ),
            filter=Condition(lambda: self.busy and not self.q_active),
        )
        # Mid-turn question picker — replaces the HUD while the agent asks.
        picker = ConditionalContainer(
            Window(
                FormattedTextControl(self._picker_fragments),
                dont_extend_height=True,
                style="class:picker",
            ),
            filter=Condition(lambda: self.q_active),
        )
        status = Window(
            FormattedTextControl(self._status_fragments), height=1, style="class:status"
        )
        root = HSplit([meta, picker, frame, status])
        style = Style.from_dict(
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
        self.app = Application(
            layout=Layout(root, focused_element=self.input),
            key_bindings=self._make_keys(),
            style=style,
            full_screen=False,
            mouse_support=False,
            erase_when_done=True,
        )

    def run(self) -> None:
        from prompt_toolkit.patch_stdout import patch_stdout

        from veles.core.user_prompt import reset_question_prompter, set_question_prompter

        # Route the agent's `ask_user` to the in-app picker (answered inside this
        # running Application — a nested prompt_toolkit app can't run under the
        # live event loop).
        qtoken = set_question_prompter(lambda q, opts=None: self._ask(q, opts))
        # patch_stdout routes all writes (rich prints + streamed tokens, from
        # this thread or the executor) ABOVE the live input box, into the
        # terminal's own scrollback. raw=True is required so rich's ANSI colour
        # sequences pass through instead of being escaped (shown as literal
        # `\x1b[...m`).
        try:
            with patch_stdout(raw=True):
                self.app.run()
        finally:
            reset_question_prompter(qtoken)

    def _spawn(self, coro) -> None:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def _invalidate_threadsafe(self) -> None:
        """Ask the app to redraw. `Application.invalidate` schedules the redraw
        on the loop, so it's safe to call from the executor thread (streaming
        callbacks) as well as the loop thread."""
        import contextlib

        with contextlib.suppress(Exception):
            self.app.invalidate()

    def _status_fragments(self):
        # The quiet bottom bar: settled mode + tokens + cache ONLY (no live
        # churn — the working HUD carries the per-request counters).
        return [
            (
                "class:status",
                f" {_settled_status(self.state)} · Shift+Tab mode · /help · "
                "Ctrl+O meta · Ctrl+D exit ",
            )
        ]

    def _meta_fragments(self):
        """The live "working…" HUD shown in the app region during a turn:
        elapsed, an approximate output-token count (chars/4 — providers only
        report exact usage in the final chunk), and tool/mode-switch activity.
        Collapsed by default; Ctrl+O expands the event list."""
        from prompt_toolkit.formatted_text import FormattedText

        elapsed = int(time.monotonic() - self.turn_start) if self.turn_start else 0
        approx = self.stream_chars // 4
        dots = "." * (1 + (self._tick % 3))
        tools = [t for k, t in self.meta_events if k == "tool"]
        modes = [t for k, t in self.meta_events if k == "mode"]
        head = f" ⏳ working{dots} · ≈{approx} tok · {len(tools)} tool(s) · {elapsed}s"
        hint = "  (Ctrl+O свернуть)" if self.meta_expanded else "  (Ctrl+O раскрыть)"
        frags: list[tuple[str, str]] = [("class:meta", head + hint + "\n")]
        if self.meta_expanded:
            for t in modes:
                frags.append(("class:meta.dim", f"     ↳ {t}\n"))
            for t in tools[-10:]:
                frags.append(("class:meta.dim", f"     ⚒ {t}\n"))
        return FormattedText(frags)

    def _picker_fragments(self):
        """The mid-turn ask_user picker rendered in the app region."""
        from prompt_toolkit.formatted_text import FormattedText

        frags: list[tuple[str, str]] = [("class:picker", f" {self.q_question}\n")]
        if self.q_free:
            frags.append(("class:picker.dim", "  введите свой вариант ниже — Enter отправит\n"))
            return FormattedText(frags)
        items = [*self.q_options, self._FREE_LABEL]
        for i, label in enumerate(items):
            sel = i == self.q_sel
            marker = "❯" if sel else " "
            frags.append(("class:picker.sel" if sel else "class:picker", f"  {marker} {label}\n"))
        frags.append(("class:picker.dim", "  ↑↓ выбор · Enter · Esc отмена\n"))
        return FormattedText(frags)

    def _push_meta(self, kind: str, text: str) -> None:
        """Meta sink for the turn callbacks (called from the executor thread)."""
        if kind == "stream":
            self.stream_chars += len(text)
        else:
            self.meta_events.append((kind, text))
        self._invalidate_threadsafe()

    async def _tick_meta(self) -> None:
        """Animate the HUD's spinner/elapsed while a turn runs."""
        while self.busy:
            self._tick += 1
            self.app.invalidate()
            await asyncio.sleep(0.3)

    def _freeze_meta(self) -> None:
        """Freeze the turn's meta into scrollback in its current (collapsed /
        expanded) form — the live HUD region is transient, so this is what
        survives in the terminal's history."""
        tools = [t for k, t in self.meta_events if k == "tool"]
        modes = [t for k, t in self.meta_events if k == "mode"]
        if not tools and not modes and not self.stream_chars:
            return
        approx = self.stream_chars // 4
        elapsed = int(time.monotonic() - self.turn_start) if self.turn_start else 0
        self.console.print(
            f"  ⋅ ≈{approx} tok · {len(tools)} tool(s) · {elapsed}s",
            style=self.theme.muted,
            markup=False,
        )
        if self.meta_expanded:
            for t in modes:
                self.console.print(f"     ↳ {t}", style=self.theme.muted, markup=False)
            for t in tools:
                self.console.print(f"     ⚒ {t}", style=self.theme.muted, markup=False)

    # --- mid-turn ask_user picker (answered inside this running app) ---

    def _ask(self, question: str, options):
        """Question prompter installed for the agent's `ask_user`. Runs in the
        executor thread: it publishes the question, wakes the UI, then blocks on
        an Event until a key handler (loop thread) supplies the answer. Returns
        None with no TTY so headless runs never block."""
        import threading

        if not sys.stdin.isatty():
            return None
        self.q_question = question
        self.q_options = list(options) if options else []
        self.q_sel = 0
        self.q_free = not self.q_options  # no options → straight to free text
        self.q_answer = None
        self.q_event = threading.Event()
        self.q_active = True
        self._invalidate_threadsafe()
        self.q_event.wait()  # blocks the executor thread, not the loop
        return self.q_answer

    def _answer(self, ans) -> None:
        ev = self.q_event
        question = self.q_question
        self.q_answer = ans
        self.q_active = False
        self.q_free = False
        self.q_event = None
        if ans is not None:
            self.console.print(f"  ⋅ {question} → {ans}", style=self.theme.muted, markup=False)
        self.app.invalidate()
        if ev is not None:
            ev.set()

    def _picker_enter(self) -> None:
        if self.q_sel >= len(self.q_options):  # the free-text sentinel row
            self.q_free = True
            self.input.text = ""
            self.app.invalidate()
            return
        self._answer(self.q_options[self.q_sel])

    def _free_submit(self) -> None:
        txt = self.input.text.strip()
        self.input.text = ""
        self._answer(txt or None)

    def _make_keys(self):
        from prompt_toolkit.filters import Condition
        from prompt_toolkit.key_binding import KeyBindings

        kb = KeyBindings()
        # Three input regimes, gated by filters so one key means different things:
        #   normal   — typing a prompt (no question pending)
        #   choosing — arrow-selecting an ask_user option
        #   freeing  — typing a free-text answer to an ask_user question
        normal = Condition(lambda: not self.q_active)
        choosing = Condition(lambda: self.q_active and not self.q_free)
        freeing = Condition(lambda: self.q_active and self.q_free)

        @kb.add("enter", filter=normal)
        def _(event) -> None:
            self._on_enter()

        @kb.add("enter", filter=choosing)
        def _(event) -> None:
            self._picker_enter()

        @kb.add("enter", filter=freeing)
        def _(event) -> None:
            self._free_submit()

        @kb.add("escape", "enter", filter=normal)  # Alt/Option+Enter → newline
        def _(event) -> None:
            self.input.buffer.insert_text("\n")

        @kb.add("up", filter=normal)
        def _(event) -> None:
            # Smart: history-backward when on the first line, else cursor up.
            # `go_to_start_of_line_if_history_changes=False` leaves the cursor at
            # the END of the recalled command (not the start).
            self.input.buffer.auto_up(count=1, go_to_start_of_line_if_history_changes=False)

        @kb.add("down", filter=normal)
        def _(event) -> None:
            self.input.buffer.auto_down(count=1, go_to_start_of_line_if_history_changes=False)

        @kb.add("up", filter=choosing)
        def _(event) -> None:
            self.q_sel = (self.q_sel - 1) % (len(self.q_options) + 1)
            self.app.invalidate()

        @kb.add("down", filter=choosing)
        def _(event) -> None:
            self.q_sel = (self.q_sel + 1) % (len(self.q_options) + 1)
            self.app.invalidate()

        for _i in range(9):

            @kb.add(str(_i + 1), filter=choosing)
            def _(event, idx=_i) -> None:
                if idx <= len(self.q_options):
                    self.q_sel = idx
                    self.app.invalidate()

        @kb.add("escape", filter=Condition(lambda: self.q_active))
        def _(event) -> None:
            self._answer(None)

        @kb.add("s-tab", filter=normal)
        def _(event) -> None:
            self.state.mode = self._next_mode(self.state.mode)
            self.app.invalidate()

        @kb.add("c-o")
        def _(event) -> None:
            self.meta_expanded = not self.meta_expanded
            self.app.invalidate()

        @kb.add("c-d")
        def _(event) -> None:
            event.app.exit()

        @kb.add("c-c")
        def _(event) -> None:
            self._on_ctrl_c(event)

        return kb

    def _on_enter(self) -> None:
        text = self.input.text.strip()
        self.input.text = ""
        if not text:
            return  # ignore empty input
        self._spawn(self._dispatch(text))

    def _on_ctrl_c(self, event) -> None:
        if self.q_active:
            self._answer(None)  # cancel the pending question
            return
        if self.busy and self.cancel_token is not None:
            self.cancel_token.cancel()  # cooperative cancel of the running turn
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

    async def _in_terminal(self, func) -> None:
        from prompt_toolkit.application import run_in_terminal

        await run_in_terminal(func)

    def _echo_user(self, text: str) -> None:
        """Echo the request into the scrollback, accent-marked as user input
        (distinct from the agent's streamed answer below it). Under
        `patch_stdout` this lands above the live input box."""
        self.console.print()
        self.console.print(f"❯ {text}", style=f"bold {self.theme.accent}", markup=False)

    async def _dispatch(self, text: str) -> None:
        if text.startswith("/"):
            await self._slash(text)
            return
        if self.busy:
            self.queue.append(text)
            self.console.print(f"  ⋅ queued: {text}", style=self.theme.muted, markup=False)
            return
        await self._run_chain(text)

    async def _slash(self, text: str) -> None:
        self._echo_user(text)
        box: dict = {}

        def _do() -> None:
            box["res"] = _handle_slash(
                text, self.registry, self.state, self.project, self.store, self.console, self.errors
            )

        # run_in_terminal: /sessions may read input (rich.Prompt.ask), which
        # needs the terminal handed back from the app.
        await self._in_terminal(_do)
        should_quit, submit = box.get("res", (False, None))
        if should_quit:
            self.app.exit()
        elif submit:
            await self._dispatch(submit)

    async def _run_chain(self, text: str) -> None:
        from veles.core.cancel import CancelToken

        self.busy = True
        self._tick = 0
        self._spawn(self._tick_meta())  # animate the working HUD while busy
        self.app.invalidate()
        loop = asyncio.get_event_loop()
        try:
            while True:
                # Reset the live meta HUD for this turn.
                self.meta_events = []
                self.stream_chars = 0
                self.turn_start = time.monotonic()
                self._echo_user(text)
                self.cancel_token = CancelToken()
                # A fresh copy of the captured parent context per turn (a Context
                # can't be run concurrently); the executor runs the turn inside it
                # so the active project / module registry / i18n reach the tools.
                turn_ctx = self._parent_ctx.run(contextvars.copy_context)
                try:
                    result = await loop.run_in_executor(
                        None, lambda c=turn_ctx, t=text: c.run(self._blocking_turn, t)
                    )
                except Exception as exc:
                    self.errors.append(str(exc))
                    self.console.print(f"\nerror: {exc}", style=self.theme.error, markup=False)
                    result = None
                if getattr(result, "stopped_reason", "") == "cancelled":
                    self.console.print("  ⋅ cancelled", style=self.theme.muted, markup=False)
                self.console.print()  # trailing blank after the streamed answer
                self._freeze_meta()  # freeze the HUD into scrollback
                _update_state_after_turn(self.state, result)
                if self.queue:
                    text = self.queue.popleft()
                else:
                    break
        finally:
            self.cancel_token = None
            self.busy = False
            self.app.invalidate()

    def _blocking_turn(self, text: str):
        """Runs in the executor thread and streams the answer live via the
        callbacks. Activates the cancel token in *this* thread so the agent's
        cooperative cancel checks see it. Returns the RunResult."""
        from veles.core.cancel import reset_cancel_token, set_cancel_token
        from veles.core.modes import ModeContext, get_mode

        tok = set_cancel_token(self.cancel_token)
        post, on_text, on_event, holder, flush = _make_turn_callbacks(
            self.console, self.theme, self.errors, on_meta=self._push_meta
        )
        try:
            ctx = ModeContext(
                state=self.state,
                project=self.project,
                factory=self.factory,
                post=post,
                on_text=on_text,
                on_event=on_event,
            )
            get_mode(self.state.mode).run_turn(text, ctx)
        finally:
            reset_cancel_token(tok)
            flush()  # render the trailing block even if the turn raised
        return holder.get("result")


def cmd_repl(args: argparse.Namespace, project: Project) -> int:
    from veles.tui.slash import build_default_registry

    runtime = _build_runtime(args, project)
    if runtime is None:
        return 2
    state, factory, store = runtime
    registry = build_default_registry(project=project)
    console = _console()
    theme = _resolve_theme(state)
    errors: list[str] = []

    try:
        _banner(console, args.provider, args.model, state.mode, theme)
        # Default: the inline Application — a settled bottom status bar (mode +
        # token/cache stats), a live "working…" HUD during generation (Ctrl+O
        # expands tool/mode activity), and the in-app ask_user picker. It pins
        # the status bar correctly over long scrolling output (rich.Live can't).
        # The blocking-prompt loop is a fallback via VELES_REPL_SIMPLE=1 for
        # terminals where the Application misbehaves.
        if os.environ.get("VELES_REPL_SIMPLE"):
            _run_simple_repl(args, project, state, factory, store, registry, console, theme, errors)
        else:
            _ReplApp(args, project, state, factory, store, registry, console, theme, errors).run()
    finally:
        store.close()
    return 0
