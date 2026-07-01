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


def _make_turn_callbacks(console, theme, errors: list[str]):
    """Build (post, on_text, on_event) for a `ModeContext`, plus a holder for
    the final `RunResult`.

    These **stream by block**: answer tokens accumulate in a buffer, and each
    completed Markdown block (paragraph, list, table, fenced code) is rendered
    formatted as soon as its terminating blank line arrives — progressive AND
    formatted. `flush()` renders the trailing block at end of turn. Dim mode
    lines print as they arrive. Under the Application's `patch_stdout`, writes
    from the executor thread appear above the live input box.

    Returns ``(post, on_text, on_event, holder, flush)``.
    """
    from veles.tui.messages import AgentError, ChatDelta, SystemLine, TurnDone

    holder: dict[str, object] = {}
    buf = [""]  # mutable string cell shared across chunks

    def _emit(chunk: str) -> None:
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
            console.print(f"  ⋅ {msg.text}", style=theme.muted, markup=False)
        elif isinstance(msg, ChatDelta):
            _emit(msg.text)
        elif isinstance(msg, AgentError):
            errors.append(str(msg.exc))
            console.print(f"\nerror: {msg.exc}", style=theme.error, markup=False)

    def on_text(text: str) -> None:
        _emit(text)

    def on_event(_event) -> None:
        return None

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


def _run_mode_turn(state, project, factory, line: str, console, errors: list[str], theme):
    """Drive one user turn through the active mode's FSM. The answer streams
    live via the callbacks; dim mode lines print as they arrive."""
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


def _run_simple_repl(
    args, project, state, factory, store, registry, console, theme, errors
) -> None:
    """Fallback loop on the blocking `PromptSession.prompt()` (set
    `VELES_REPL_SIMPLE=1`). No live-during-generation input; kept as a safety
    net for terminals where the inline Application misbehaves."""
    from prompt_toolkit.formatted_text import HTML

    prompt_html = HTML(f'<style fg="{theme.accent}"><b>❯</b></style> ')
    prompt_session = _make_prompt_session(project, registry, state)
    console.rule(style=theme.border, characters="─")
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

    def __init__(self, args, project, state, factory, store, registry, console, theme, errors):
        from prompt_toolkit.application import Application
        from prompt_toolkit.completion import Completer, Completion
        from prompt_toolkit.formatted_text import FormattedText
        from prompt_toolkit.history import FileHistory
        from prompt_toolkit.layout import HSplit, Layout, Window
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
        status = Window(
            FormattedTextControl(self._status_fragments), height=1, style="class:status"
        )
        root = HSplit([frame, status])
        style = Style.from_dict(
            {
                "frame.border": theme.border,
                "prompt": f"bold {theme.accent}",
                "status": theme.muted,
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

        # patch_stdout routes all writes (rich prints + streamed tokens, from
        # this thread or the executor) ABOVE the live input box, into the
        # terminal's own scrollback.
        with patch_stdout():
            self.app.run()

    def _spawn(self, coro) -> None:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def _status_fragments(self):
        s = self.state
        sid = (s.session_id or "new")[:8]
        flag = "working… · " if self.busy else ""
        tok = f" · {s.last_turn_total_tokens} tok" if s.last_turn_total_tokens else ""
        return [
            (
                "class:status",
                f" {flag}mode:{s.mode} · {s.provider_name}:{s.model} · session:{sid}{tok}"
                " · Shift+Tab mode · /help · Ctrl+D exit ",
            )
        ]

    def _make_keys(self):
        from prompt_toolkit.key_binding import KeyBindings

        kb = KeyBindings()

        @kb.add("enter")
        def _(event) -> None:
            self._on_enter()

        @kb.add("escape", "enter")  # Alt/Option+Enter inserts a newline
        def _(event) -> None:
            self.input.buffer.insert_text("\n")

        @kb.add("up")
        def _(event) -> None:
            # Smart: history-backward when on the first line, else cursor up.
            # `go_to_start_of_line_if_history_changes=False` leaves the cursor at
            # the END of the recalled command (not the start).
            self.input.buffer.auto_up(count=1, go_to_start_of_line_if_history_changes=False)

        @kb.add("down")
        def _(event) -> None:
            self.input.buffer.auto_down(count=1, go_to_start_of_line_if_history_changes=False)

        @kb.add("s-tab")
        def _(event) -> None:
            self.state.mode = self._next_mode(self.state.mode)
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
        self.app.invalidate()
        loop = asyncio.get_event_loop()
        try:
            while True:
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
            self.console, self.theme, self.errors
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
        if os.environ.get("VELES_REPL_SIMPLE"):
            _run_simple_repl(args, project, state, factory, store, registry, console, theme, errors)
        else:
            _ReplApp(args, project, state, factory, store, registry, console, theme, errors).run()
    finally:
        store.close()
    return 0
