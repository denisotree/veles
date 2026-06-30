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
import datetime as _dt
import sys
import time

from veles.core.project import Project

# Window inside which a second Ctrl+C at the prompt is treated as exit.
_CTRL_C_EXIT_WINDOW_S = 1.5


def _console():
    from rich.console import Console

    # force_terminal so colours survive when piped; the REPL is interactive.
    return Console()


def _fmt_ts(ts: float) -> str:
    return _dt.datetime.fromtimestamp(ts, tz=_dt.UTC).astimezone().strftime("%Y-%m-%d %H:%M")


def _resolve_theme(state):
    """The active TUI theme (user config → fallback), reused for the REPL's
    colours so `veles repl` matches the user's installed theme."""
    from veles.cli.tui_theme import THEMES, load_theme

    return load_theme(getattr(state, "theme_name", "") or "everforest") or THEMES["everforest"]


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
            sys_chunks.append(extra_system.strip())
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


def _make_turn_callbacks(state, errors: list[str]):
    """Build (post, on_text, on_event) for a `ModeContext`, plus a holder for
    the final `RunResult` and the accumulators for the dim system lines and the
    answer text.

    The turn is rendered *after* it completes (so the answer can be pretty-
    printed as Markdown), so these callbacks accumulate instead of printing.
    Modes never import Textual — they only call these — so the same FSM drives
    the REPL.

    Returns ``(post, on_text, on_event, holder, sys_lines, answer)``.
    """
    from veles.tui.messages import AgentError, ChatDelta, SystemLine, TurnDone

    holder: dict[str, object] = {}
    sys_lines: list[str] = []
    answer: list[str] = []

    def post(msg) -> None:
        if isinstance(msg, TurnDone):
            holder["result"] = msg.result
        elif isinstance(msg, SystemLine):
            sys_lines.append(msg.text)
        elif isinstance(msg, ChatDelta):
            answer.append(msg.text)
        elif isinstance(msg, AgentError):
            errors.append(str(msg.exc))
            answer.append(f"\n\n**error:** {msg.exc}\n")

    def on_text(text: str) -> None:
        answer.append(text)

    def on_event(_event) -> None:
        return None

    return post, on_text, on_event, holder, sys_lines, answer


def _render_answer(console, text: str) -> None:
    """Pretty-print the assistant answer as Markdown — headings, lists, tables,
    links, bold/italic, and syntax-highlighted code blocks. Falls back to plain
    text if rendering ever raises so a glitch never eats the answer."""
    from rich.markdown import Markdown

    try:
        console.print(Markdown(text))
    except Exception:
        console.print(text, markup=False)


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


def _run_mode_turn(state, project, factory, line: str, console, errors: list[str], theme):
    """Drive one user turn through the active mode's FSM, then render the
    answer as Markdown. Shows a spinner while the model works; dim mode lines
    and the formatted answer print once the turn completes."""
    from veles.core.modes import ModeContext, get_mode

    post, on_text, on_event, holder, sys_lines, answer = _make_turn_callbacks(state, errors)
    ctx = ModeContext(
        state=state,
        project=project,
        factory=factory,
        post=post,
        on_text=on_text,
        on_event=on_event,
    )
    interrupted = False
    try:
        with console.status(f"[{theme.accent}]working…[/]", spinner="dots"):
            get_mode(state.mode).run_turn(line, ctx)
    except KeyboardInterrupt:
        interrupted = True

    for sl in sys_lines:
        console.print(f"  ⋅ {sl}", style=theme.muted, markup=False)
    text = "".join(answer).strip()
    result = holder.get("result")
    if not text and result is not None:
        text = (getattr(result, "text", "") or "").strip()
    if text:
        _render_answer(console, text)
    if interrupted:
        console.print("  ⋅ interrupted", style=theme.muted, markup=False)
    return result


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
        sid = (state.session_id or "new")[:8]
        bits = f" mode:{state.mode} · {state.provider_name}:{state.model} · session:{sid}"
        if state.last_turn_total_tokens:
            bits += f" · {state.last_turn_total_tokens} tok"
        return bits + " · Shift+Tab mode · /help · Ctrl+D exit "

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


def cmd_repl(args: argparse.Namespace, project: Project) -> int:
    from prompt_toolkit.formatted_text import HTML

    from veles.tui.slash import build_default_registry

    runtime = _build_runtime(args, project)
    if runtime is None:
        return 2
    state, factory, store = runtime
    registry = build_default_registry(project=project)
    console = _console()
    theme = _resolve_theme(state)
    errors: list[str] = []
    # Themed prompt: the accent-coloured "❯", with a thin rule above it framing
    # the input and separating it from the generated output above.
    prompt_html = HTML(f'<style fg="{theme.accent}"><b>❯</b></style> ')

    last_ctrl_c = 0.0
    try:
        _banner(console, args.provider, args.model, state.mode, theme)
        prompt_session = _make_prompt_session(project, registry, state)
        console.rule(style=theme.border, characters="─")

        while True:
            try:
                line = prompt_session.prompt(prompt_html)
            except KeyboardInterrupt:
                # Double Ctrl+C (within the window) exits, like Ctrl+D; a single
                # one just cancels the current line.
                now = time.monotonic()
                if now - last_ctrl_c <= _CTRL_C_EXIT_WINDOW_S:
                    break
                last_ctrl_c = now
                console.print("(press Ctrl+C again or Ctrl+D to exit)", style=theme.muted)
                continue
            except EOFError:
                break  # Ctrl+D exits.

            line = line.strip()
            if not line:
                continue  # ignore empty input

            if line.startswith("/"):
                should_quit, submit = _handle_slash(
                    line, registry, state, project, store, console, errors
                )
                if should_quit:
                    break
                if not submit:
                    continue
                line = submit  # fall through and run the command's prompt

            console.print()
            try:
                result = _run_mode_turn(state, project, factory, line, console, errors, theme)
            except Exception as exc:
                errors.append(str(exc))
                console.print(f"error: {exc}", style=theme.error, markup=False)
                console.rule(style=theme.border, characters="─")
                continue
            _update_state_after_turn(state, result)
            # Separate this turn's output from the next input.
            console.rule(style=theme.border, characters="─")
    finally:
        store.close()
    return 0
