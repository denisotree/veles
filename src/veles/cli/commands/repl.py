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
import atexit
import contextvars
import os
import sys
import time
from collections import deque
from pathlib import Path

from veles.cli.repl.pickers.helpers import (  # noqa: F401  (_print_model_list is a test shim)
    _at_trigger_boundary,
    _filter_files,
    _filter_models,
    _new_paste_filename,
    _print_model_list,
)
from veles.cli.repl.terminal import (
    _CTRL_C_EXIT_WINDOW_S,
    _KITTY_ENABLE,
    _banner,
    _console,
    _kitty_disable_keyboard,
    _print_resume_recap,
    _register_kitty_sequences,
    _resolve_theme,
    _settled_status,
    _tool_row,
)
from veles.cli.repl.turn import (  # noqa: F401  (some names are re-export shims)
    _REPL_BEHAVIOUR_BLOCK,
    _handle_slash,
    _make_turn_callbacks,
    _render_answer,
    _render_edit_diff,
    _repl_turn_system_prompt,
    _run_mode_turn,
    _run_repl_post_turn_hooks,
    _split_blocks,
    _update_state_after_turn,
)
from veles.core.i18n import t
from veles.core.project import Project

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


def _build_runtime(args: argparse.Namespace, project: Project):
    """Resolve provider/model, gate the API key, and build the per-turn Agent
    factory + AppState + store for the interactive REPL.

    Returns ``(state, factory, store)`` or ``None`` when the key gate fails.
    """
    from veles.cli import (
        _PLANNING_TOOLS,
        _PROVIDER_API_KEY_ENVS,
        _RUN_TOOLS,
        _build_compressor,
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
    from veles.core.session_state import AppState

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

    def factory(state, *, mode_override=None, extra_system=None, query=None):
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
        # M191: `query` (the raw user prompt, passed by the mode) drives the
        # per-turn `<memory-context>` recall — empty before M191, so the REPL
        # never recalled project memory.
        system_prompt = _repl_turn_system_prompt(
            args, project, mode=mode, query=query, extra_system=extra_system
        )
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

    def subagent_factory(*, system_prompt, tools):
        """Build an ephemeral, context-isolated worker for the `delegate` tool.
        Same provider/model as the root; a NARROW registry (scoped from the FULL
        global registry so wiki_* etc. are reachable); no SessionStore (workers
        are disposable)."""
        from veles.core.tools.registry import registry as _global_registry

        return Agent(
            provider=provider,
            registry=_global_registry.subset(tools),
            model=args.model,
            max_iterations=min(args.max_iterations, 20),
            system_prompt=system_prompt,
            store=None,
            compressor=compressor,
            hard_ceiling_tokens=default_hard_ceiling_for(args.model),
        )

    from veles.core.user_config import load_user_config

    # -c / --continue: resume this project's most recent NON-EMPTY session (one
    # with at least one turn — skip empty sessions from an aborted launch). An
    # explicit --resume ID wins. Nothing to resume → start fresh.
    resume_id = getattr(args, "resume", None)
    if resume_id is None and getattr(args, "continue_last", False):
        recent = [s for s in store.list_sessions(limit=50) if s.turn_count > 0]
        if recent:
            latest = recent[0]  # list_sessions is ordered by last_activity DESC
            resume_id = latest.id
            print(f"continuing session {resume_id[:8]} ({latest.title or 'untitled'})")
        else:
            print("no previous session with content in this project — starting fresh")

    user_cfg = load_user_config()
    state = AppState(
        session_id=resume_id,
        provider_name=args.provider,
        model=args.model,
        theme_name=(user_cfg.tui_theme if user_cfg and user_cfg.tui_theme else "everforest"),
    )
    return state, factory, store, subagent_factory


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

    free_label = t("repl.free_choice")
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
        lines.append(("ansibrightblack", f"\n  {t('repl.picker_hint')}\n"))
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
        answer = prompt(_pt_html(theme, f"  {t('repl.your_answer')} ❯ ")).strip()
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
    args, project, state, factory, store, registry, console, theme, errors, subagent_factory=None
) -> None:
    """Fallback loop on the blocking `PromptSession.prompt()` (set
    `VELES_REPL_SIMPLE=1`). No live-during-generation input; kept as a safety
    net for terminals where the inline Application misbehaves."""
    from prompt_toolkit.formatted_text import HTML

    from veles.core.orchestration.delegation import (
        reset_subagent_factory,
        set_subagent_factory,
    )
    from veles.core.user_prompt import reset_question_prompter, set_question_prompter

    prompt_html = HTML(f'<style fg="{theme.accent}"><b>❯</b></style> ')
    prompt_session = _make_prompt_session(project, registry, state)
    # Route agent `ask_user` questions to an inline picker / free-text prompt.
    qtoken = set_question_prompter(lambda q, opts=None: _ask_repl(console, theme, q, opts))
    dtoken = set_subagent_factory(subagent_factory) if subagent_factory is not None else None
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
        if dtoken is not None:
            reset_subagent_factory(dtoken)


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
        # M191: learning loop on the completed turn (parity with `veles run`).
        _run_repl_post_turn_hooks(args, project, result)
        console.rule(style=theme.border, characters="─")


class _ReplApp:
    """Inline prompt_toolkit Application (no alt-screen). A bordered input box
    stays live while a turn runs in a background executor; input typed during
    generation is queued and drained on completion. Output renders ABOVE the
    box via `run_in_terminal`, landing in the terminal's own scrollback — so
    native scroll / selection / copy are preserved.
    """

    # The final picker item — selecting it switches to free-text entry.

    def __init__(
        self,
        args,
        project,
        state,
        factory,
        store,
        registry,
        console,
        theme,
        errors,
        subagent_factory=None,
    ):
        from prompt_toolkit.application import Application
        from prompt_toolkit.completion import Completer, Completion
        from prompt_toolkit.filters import Condition
        from prompt_toolkit.formatted_text import FormattedText
        from prompt_toolkit.history import FileHistory
        from prompt_toolkit.layout import ConditionalContainer, HSplit, Layout, Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.layout.dimension import Dimension
        from prompt_toolkit.widgets import Frame, TextArea

        from veles.core.modes import next_mode

        _register_kitty_sequences()  # parse CSI-u once the protocol is enabled in run()

        self.args = args
        self.project = project
        self.state = state
        self.factory = factory
        self.store = store
        self.registry = registry
        self.console = console
        self.theme = theme
        self.errors = errors
        self._subagent_factory = subagent_factory  # for the `delegate` tool
        self.busy = False
        self.queue: deque[str] = deque()
        self._last_submitted = ""  # the running turn's prompt, for Esc-to-restore
        self.cancel_token = None
        self._last_ctrl_c = 0.0
        self._next_mode = next_mode
        self._tasks: set = set()  # keep strong refs so tasks aren't GC'd mid-flight
        # --- live-generation meta HUD state (reset per turn) ---
        self.meta_events: list[tuple[str, str]] = []  # ("mode"|"tool", text)
        self.meta_expanded = False
        self.stream_chars = 0
        self.turn_start = 0.0
        self.turn_elapsed = 0.0  # frozen duration once the turn finishes
        # Per-tool inspector rows (Ctrl+I/Ctrl+O expanded view), keyed by
        # tool_call_id → {"name", "start", "end", "status"}. `end` is None
        # while the matching tool_result hasn't arrived yet (still running).
        # Insertion order is display order (dicts preserve it).
        self.tool_activity: dict[str, dict[str, object]] = {}
        self._tick = 0
        # --- mid-turn ask_user picker state (answered inside THIS app; a nested
        # prompt_toolkit Application can't run under the live loop) ---
        self.q_active = False
        self.q_free = False
        self.q_allow_free = False  # show the free-choice row (ask_user only)
        self.q_question = ""
        self.q_options: list[str] = []
        self.q_values: list[str] | None = None  # decision values (permission prompt)
        self.q_sel = 0
        self.q_answer: str | None = None
        self.q_event = None
        # --- /model picker state (loop-thread driven; the input box is its live
        # filter). Mutually exclusive with q_active by construction — you can't
        # submit a slash while a question is pending. ---
        self.mp_active = False
        self.mp_loading = False
        self.mp_models: list[str] = []
        self.mp_source = ""
        self.mp_sel = 0
        # --- @ file picker state (mirrors the /model picker, but is triggered
        # inline by typing `@` at a word boundary — not via a slash command —
        # and, unlike the model picker, keeps the `@`+filter text IN the input
        # box rather than clearing it, since Enter re-inserts a path after it).
        self.fp_active = False
        self.fp_files: list[str] = []
        self.fp_sel = 0
        # --- /theme picker state (mirrors the /model picker, but synchronous —
        # `list_themes()` is a dict + directory glob, no network hop like the
        # provider fetch behind /model).
        self.tp_active = False
        self.tp_themes: list[str] = []
        self.tp_sel = 0
        # Capture the caller's ContextVars NOW (constructed inside the CLI's
        # `set_active_project` scope) so background turns can re-enter them —
        # `run_in_executor` does not copy context, and without the active
        # project the tools resolve wrong paths (run_shell cwd → ~/.veles/skills).
        self._parent_ctx = contextvars.copy_context()

        extra = ("/sessions", "/errors", "/resume")
        outer = self

        class _SlashCompleter(Completer):
            def get_completions(self, document, complete_event):
                # No slash completion while the model/file filter owns the input box.
                if outer.mp_active or outer.fp_active or outer.tp_active:
                    return
                text = document.text_before_cursor
                if not text.startswith("/") or " " in text:
                    return
                for name in [*registry.names(), *extra]:
                    if name.startswith(text):
                        yield Completion(name, start_position=-len(text))

        # Input history is managed explicitly (see _history_up/_down): the
        # Buffer's own FileHistory reloads its working-lines asynchronously and
        # didn't resync a just-submitted command in this embedded Application, so
        # Up recalled stale entries. We keep a plain oldest→newest list, persist
        # to the same `repl_history` file for cross-run recall, and drive Up/Down
        # ourselves. The TextArea therefore takes NO history.
        self._hist_store = FileHistory(str(project.state_dir / "repl_history"))
        self._hist: list[str] = list(reversed(list(self._hist_store.load_history_strings())))
        self._hist_pos: int | None = None  # None → editing a fresh line
        self._hist_draft = ""  # the in-progress line stashed when recall starts
        self.input = TextArea(
            prompt=FormattedText([("class:prompt", "❯ ")]),
            multiline=True,
            wrap_lines=True,
            height=Dimension(min=1, max=10),
            # Size to content: 1 line when empty, growing per line up to max=10.
            # Without this the Window extends to fill toward max even when empty
            # (its default dont_extend_height is False).
            dont_extend_height=True,
            completer=_SlashCompleter(),
            complete_while_typing=True,
            style="class:input",
        )
        # While the /model picker is open, typing in the input box filters the
        # list — reset the selection to the top on every keystroke.
        self.input.buffer.on_text_changed += self._on_input_changed
        frame = Frame(self.input)
        # Live generation HUD — shown while a turn runs AND afterwards for the
        # last turn (until the next prompt resets it), so Ctrl+O expand/collapse
        # works both during generation and while idle. Hidden only when a
        # question picker is up. dont_extend_height → one line collapsed.
        meta = ConditionalContainer(
            Window(
                FormattedTextControl(self._meta_fragments),
                dont_extend_height=True,
                style="class:meta",
            ),
            filter=Condition(
                lambda: (
                    bool(self.busy or self.stream_chars or self.meta_events)
                    and not self.q_active
                    and not self.mp_active
                    and not self.fp_active
                    and not self.tp_active
                )
            ),
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
        # /model filterable picker — shown when the user opens it.
        model_picker = ConditionalContainer(
            Window(
                FormattedTextControl(self._mp_fragments),
                dont_extend_height=True,
                style="class:picker",
            ),
            filter=Condition(lambda: self.mp_active),
        )
        # @ file picker — shown while typing an `@` file reference.
        file_picker = ConditionalContainer(
            Window(
                FormattedTextControl(self._fp_fragments),
                dont_extend_height=True,
                style="class:picker",
            ),
            filter=Condition(lambda: self.fp_active),
        )
        # /theme filterable picker — shown when the user opens it.
        theme_picker = ConditionalContainer(
            Window(
                FormattedTextControl(self._tp_fragments),
                dont_extend_height=True,
                style="class:picker",
            ),
            filter=Condition(lambda: self.tp_active),
        )
        status = Window(
            FormattedTextControl(self._status_fragments), height=1, style="class:status"
        )
        root = HSplit([meta, picker, model_picker, file_picker, theme_picker, frame, status])
        style = self._build_style(theme)
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

        from veles.core.critical_ops import reset_critical_confirmer, set_critical_confirmer
        from veles.core.orchestration.delegation import (
            reset_subagent_factory,
            set_subagent_factory,
        )
        from veles.core.permission.prompt import reset_prompter, set_prompter
        from veles.core.user_prompt import reset_question_prompter, set_question_prompter

        # Route EVERY mid-turn prompt through the in-app picker (answered inside
        # this running Application — a nested prompt_toolkit app can't run under
        # the live event loop, and any stdin input() hangs it):
        #   - ask_user (the agent's clarifying questions)
        #   - the unified permission prompt (trust ladder + approval)
        #   - confirm_critical (M39 hard-confirm for DESTRUCTIVE ops like
        #     delete_file / user-global writes) — else its input("Confirm: ")
        #     blocks the executor thread and the whole REPL hangs.
        qtoken = set_question_prompter(lambda q, opts=None: self._ask(q, opts))
        ptoken = set_prompter(self._permission_prompt)
        ctoken = set_critical_confirmer(self._confirm_critical)
        # The `delegate` tool builds workers via this factory (holds provider/model).
        dtoken = (
            set_subagent_factory(self._subagent_factory)
            if self._subagent_factory is not None
            else None
        )
        # Re-snapshot the context AFTER installing the prompters: they're
        # ContextVars, and the executor runs each turn in a copy of _parent_ctx.
        # The __init__ snapshot predates these set()s, so without re-capturing
        # here the turn thread would see the DEFAULT prompters (which render
        # nested Applications) and corrupt the terminal. (This scope still holds
        # the active project.)
        self._parent_ctx = contextvars.copy_context()

        # Enable the kitty keyboard protocol once pt has taken over the terminal
        # (in `pre_run`, after raw mode is set), so Shift+Enter arrives as a
        # distinct CSI-u sequence. Pop it on every exit path + an atexit backstop.
        def _enable_kitty() -> None:
            try:
                if sys.stdout.isatty():
                    self.app.output.write_raw(_KITTY_ENABLE)
                    self.app.output.flush()
            except Exception:
                pass

        atexit.register(_kitty_disable_keyboard)
        # patch_stdout routes all writes (rich prints + streamed tokens, from
        # this thread or the executor) ABOVE the live input box, into the
        # terminal's own scrollback. raw=True is required so rich's ANSI colour
        # sequences pass through instead of being escaped (shown as literal
        # `\x1b[...m`).
        try:
            with patch_stdout(raw=True):
                self.app.run(pre_run=_enable_kitty)
        finally:
            _kitty_disable_keyboard()
            reset_question_prompter(qtoken)
            reset_prompter(ptoken)
            reset_critical_confirmer(ctoken)
            if dtoken is not None:
                reset_subagent_factory(dtoken)

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

    # --- mid-turn pickers (ask_user + permission), answered inside this app ---

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
        self.q_values = None  # answer IS the chosen option string
        self.q_allow_free = bool(options)  # options → offer a free-text row too
        self.q_sel = 0
        self.q_free = not self.q_options  # no options → straight to free text
        self.q_answer = None
        self.q_event = threading.Event()
        self.q_active = True
        self._invalidate_threadsafe()
        self.q_event.wait()  # blocks the executor thread, not the loop
        return self.q_answer

    def _confirm_critical(self, op: str, summary: str) -> bool:
        """M39 hard-confirm for DESTRUCTIVE ops (delete_file, user-global
        writes), answered inside THIS app as a yes/no picker — the default
        confirmer reads `input()` from stdin, which hangs the executor thread
        under the running Application. Runs in the executor thread; blocks on the
        picker Event. Refuses (False) with no TTY, and defaults the highlight to
        Cancel so a stray Enter never deletes."""
        import threading

        if not sys.stdin.isatty():
            return False
        self.console.print()
        self.console.print(f"⚠ {op}", style=self.theme.error, markup=False)
        if summary:
            self.console.print(f"  {summary}", style=self.theme.muted, markup=False)
        self.q_question = t("repl.confirm_critical", op=op)
        self.q_options = [t("repl.confirm_yes"), t("repl.confirm_cancel")]
        self.q_values = ["yes", "no"]
        self.q_allow_free = False
        self.q_free = False
        self.q_sel = 1  # default highlight = Cancel (safe)
        self.q_answer = None
        self.q_event = threading.Event()
        self.q_active = True
        self._invalidate_threadsafe()
        self.q_event.wait()
        return self.q_answer == "yes"  # Esc/cancel → None → False (deny)

    def _permission_prompt(self, req):
        """Unified permission prompter (trust ladder + approval), installed so a
        sensitive tool's decision is answered inside THIS app instead of the
        default nested-Application menu (which corrupts the terminal). Runs in
        the executor thread and blocks on the same picker Event as `_ask`. Denies
        with no TTY so headless runs never block."""
        import threading

        from veles.core.permission.prompt import PromptAnswer, format_prompt_body

        if not sys.stdin.isatty():
            return PromptAnswer(decision="deny")
        # The tool / reason / arguments go to scrollback; the picker shows only
        # the ladder options (mirrors the default menu's layout).
        self.console.print()
        self.console.print(format_prompt_body(req), style=self.theme.muted, markup=False)
        if req.kind == "trust":
            labels = [
                "Once (this call only)",
                "Always for this project",
                "Always everywhere",
                "Refuse",
            ]
            values = ["allow_once", "allow_project", "allow_global", "deny"]
        else:  # approval — turn-scoped: only allow-once / deny
            labels = ["Allow once", "Refuse"]
            values = ["allow_once", "deny"]
        self.q_question = t("repl.permission_allow", tool=req.tool_name)
        self.q_options = labels
        self.q_values = values
        self.q_allow_free = False
        self.q_free = False
        self.q_sel = 0
        self.q_answer = None
        self.q_event = threading.Event()
        self.q_active = True
        self._invalidate_threadsafe()
        self.q_event.wait()
        return PromptAnswer(decision=self.q_answer or "deny")  # Esc/None → deny

    def _picker_rows(self) -> int:
        """Total selectable rows: options plus the free-text sentinel if shown."""
        return len(self.q_options) + (1 if self.q_allow_free else 0)

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
        if self.q_allow_free and self.q_sel >= len(self.q_options):  # free-text row
            self.q_free = True
            self.input.text = ""
            self.app.invalidate()
            return
        idx = min(self.q_sel, len(self.q_options) - 1) if self.q_options else 0
        # Answer the mapped decision value (permission) or the option (ask_user).
        self._answer(self.q_values[idx] if self.q_values is not None else self.q_options[idx])

    # --- /model picker (filterable, driven inside this Application) ---

    def _on_input_changed(self, _buffer) -> None:
        # While the model picker is open the input box is the filter; reset the
        # highlighted row to the top on each keystroke so the selection tracks
        # the freshly-filtered list.
        if self.mp_active:
            self.mp_sel = 0
            self.app.invalidate()
        if self.fp_active:
            # The `@` file picker shares the box with regular typing (the `@`
            # + filter text stays in the prompt) — if the user backspaces past
            # the `@` that opened it, close quietly rather than filtering "".
            if "@" not in self.input.text:
                self._fp_close()
            else:
                self.fp_sel = 0
                self.app.invalidate()
        if self.tp_active:
            self.tp_sel = 0
            self.app.invalidate()

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

    # --- Ctrl+V image paste (M187 Task 7) ---

    def _paste_clipboard(self) -> None:
        """An image on the clipboard is saved under `.veles/tmp/paste/` and
        referenced via `@<relative-path>` inserted at the cursor — the same
        reference syntax the `@` file picker inserts. Falls back to a plain
        text paste when the clipboard holds no image. Both clipboard ops are
        best-effort (see `cli/repl/clipboard.py`) and no-op silently when the
        platform/tooling doesn't support them. Same no-TTY guard as `_ask`/
        `_confirm_critical` so a headless run degrades instead of hanging."""
        from veles.cli.repl.clipboard import paste_image, paste_text

        if not sys.stdin.isatty():
            return
        paste_dir = self.project.tmp_dir / "paste"
        target = paste_dir / _new_paste_filename()
        if paste_image(target):
            try:
                rel = target.relative_to(self.project.root).as_posix()
            except ValueError:
                rel = target.as_posix()
            doc = self.input.buffer.document
            before, after = doc.text_before_cursor, doc.text_after_cursor
            ref = f"@{rel} "
            self.input.text = f"{before}{ref}{after}"
            self.input.buffer.cursor_position = len(before) + len(ref)
            return
        text = paste_text()
        if text:
            # Same document-splice shape as the image-ref branch above (and
            # `_fp_pick`) rather than `Buffer.insert_text` — that path also
            # kicks off the completer's background task, which needs a
            # running Application event loop.
            doc = self.input.buffer.document
            before, after = doc.text_before_cursor, doc.text_after_cursor
            self.input.text = f"{before}{text}{after}"
            self.input.buffer.cursor_position = len(before) + len(text)

    # --- @ file picker (filterable, triggered inline by typing `@`) ---

    # Rows shown at once — capped at 9 so digit quick-select (1-9) maps
    # 1:1 onto the printed row numbers, mirroring the ask_user picker.
    _FP_WINDOW = 9

    def _open_file_picker(self, root: Path | None = None) -> None:
        """Populate the candidate list and switch the input box into filing
        mode. Synchronous — `iter_project_files` is a plain filesystem walk,
        unlike the /model picker's network fetch, so no executor hop needed."""
        from veles.cli.repl.file_index import iter_project_files

        self.fp_active = True
        self.fp_sel = 0
        try:
            self.fp_files = [p.as_posix() for p in iter_project_files(root or self.project.root)]
        except OSError:
            self.fp_files = []
        self.app.invalidate()

    def _fp_filter_text(self) -> str:
        """The filter is whatever follows the LAST `@` before the cursor —
        the `@` itself (and anything before it) stays put while filtering,
        and anything after the cursor (e.g. the rest of a multi-line
        Alt+Enter-composed message) is ignored rather than pollute the
        filter token."""
        before_cursor = self.input.buffer.document.text_before_cursor
        idx = before_cursor.rfind("@")
        return before_cursor[idx + 1 :] if idx != -1 else ""

    def _fp_filtered(self) -> list[str]:
        return _filter_files(self.fp_files, self._fp_filter_text())

    def _fp_window_start(self, filtered_len: int) -> int:
        window = self._FP_WINDOW
        if filtered_len <= window:
            return 0
        sel = max(0, min(self.fp_sel, filtered_len - 1))
        return max(0, min(sel - window // 2, filtered_len - window))

    def _fp_fragments(self):
        from prompt_toolkit.formatted_text import FormattedText

        if not self.fp_files:
            return FormattedText([("class:picker.dim", f" {t('repl.no_files')}\n")])
        filtered = self._fp_filtered()
        header = t("repl.file_header", count=len(self.fp_files))
        frags: list[tuple[str, str]] = [("class:picker", f" {header}\n")]
        if not filtered:
            frags.append(("class:picker.dim", f"  {t('repl.no_matches')}\n"))
            return FormattedText(frags)
        window = self._FP_WINDOW
        start = self._fp_window_start(len(filtered))
        sel = max(0, min(self.fp_sel, len(filtered) - 1))
        for i in range(start, min(start + window, len(filtered))):
            path = filtered[i]
            is_sel = i == sel
            marker = "❯" if is_sel else " "
            row_no = i - start + 1
            frags.append(
                ("class:picker.sel" if is_sel else "class:picker", f"  {marker} {row_no}. {path}\n")
            )
        if len(filtered) > window:
            frags.append(("class:picker.dim", f"  {t('repl.more_matches', count=len(filtered))}\n"))
        return FormattedText(frags)

    def _fp_move(self, delta: int) -> None:
        n = len(self._fp_filtered())
        if n:
            self.fp_sel = (max(0, min(self.fp_sel, n - 1)) + delta) % n
        self.app.invalidate()

    def _fp_select_row(self, idx: int) -> None:
        """Digit quick-select: `idx` is 0-based within the CURRENTLY displayed
        window, matching the 1-based row numbers `_fp_fragments` prints."""
        filtered = self._fp_filtered()
        start = self._fp_window_start(len(filtered))
        row = start + idx
        if row < len(filtered):
            self.fp_sel = row
            self.app.invalidate()

    def _fp_pick(self) -> None:
        filtered = self._fp_filtered()
        if not filtered:
            return
        path = filtered[max(0, min(self.fp_sel, len(filtered) - 1))]
        doc = self.input.buffer.document
        before, after = doc.text_before_cursor, doc.text_after_cursor
        idx = before.rfind("@")
        prefix = before[:idx] if idx != -1 else before
        # Preserve whatever came after the cursor verbatim (e.g. the rest of
        # a multi-line message) instead of truncating it.
        new_text = f"{prefix}@{path}{after}"
        self.input.text = new_text
        self.input.buffer.cursor_position = len(prefix) + 1 + len(path)
        self._fp_close()

    def _fp_cancel(self) -> None:
        self._fp_close()

    def _fp_close(self) -> None:
        self.fp_active = False
        self.fp_files = []
        self.app.invalidate()

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

    def _free_submit(self) -> None:
        txt = self.input.text.strip()
        self.input.text = ""
        self._answer(txt or None)

    def _make_keys(self):
        from prompt_toolkit.filters import Condition
        from prompt_toolkit.key_binding import KeyBindings

        kb = KeyBindings()
        # Input regimes, gated by filters so one key means different things:
        #   normal   — typing a prompt (no picker up)
        #   choosing — arrow-selecting an ask_user option
        #   freeing  — typing a free-text answer to an ask_user question
        #   modeling — filtering/selecting in the /model picker
        #   filing   — filtering/selecting in the @ file picker
        #   theming  — filtering/selecting in the /theme picker
        normal = Condition(
            lambda: (
                not self.q_active
                and not self.mp_active
                and not self.fp_active
                and not self.tp_active
            )
        )
        choosing = Condition(lambda: self.q_active and not self.q_free)
        freeing = Condition(lambda: self.q_active and self.q_free)
        modeling = Condition(lambda: self.mp_active)
        filing = Condition(lambda: self.fp_active)
        theming = Condition(lambda: self.tp_active)

        @kb.add("enter", filter=normal)
        def _(event) -> None:
            self._on_enter()

        @kb.add("enter", filter=choosing)
        def _(event) -> None:
            self._picker_enter()

        @kb.add("enter", filter=freeing)
        def _(event) -> None:
            self._free_submit()

        # Alt/Option+Enter → newline. NOT while busy: an active escape-prefix
        # binding makes a lone Esc a pending prefix, so Esc-to-stop-generation
        # would never resolve. During a turn you're queuing, not composing.
        @kb.add(
            "escape",
            "enter",
            filter=Condition(
                lambda: (
                    not self.q_active
                    and not self.mp_active
                    and not self.fp_active
                    and not self.tp_active
                    and not self.busy
                )
            ),
        )
        def _(event) -> None:
            self.input.buffer.insert_text("\n")

        @kb.add("c-j", filter=normal)  # Ctrl+J = LF (0x0a) — a newline key that
        def _(event) -> None:  # is distinct from Enter (0x0d) in EVERY terminal,
            self.input.buffer.insert_text("\n")  # unlike Shift+Enter.

        @kb.add("f24", filter=normal)  # Shift+Enter (CSI-u terminals) → newline
        def _(event) -> None:
            self.input.buffer.insert_text("\n")

        @kb.add("up", filter=normal)
        def _(event) -> None:
            self._history_up()

        @kb.add("down", filter=normal)
        def _(event) -> None:
            self._history_down()

        @kb.add("@", filter=normal)
        def _(event) -> None:
            # Type the `@` as usual, then — only at a word boundary (start of
            # input / after whitespace) — open the file picker. Mid-word (an
            # email address) it's just a character. Never open while a turn is
            # running (`busy`): a mid-turn `_ask`/`_permission_prompt` can flip
            # `q_active` on top of an already-open picker, putting two
            # mutually-exclusive filter states active at once.
            before = self.input.buffer.document.text_before_cursor
            boundary = _at_trigger_boundary(before)
            self.input.buffer.insert_text("@")
            if boundary and not self.busy:
                self._open_file_picker()

        @kb.add("up", filter=choosing)
        def _(event) -> None:
            self.q_sel = (self.q_sel - 1) % self._picker_rows()
            self.app.invalidate()

        @kb.add("down", filter=choosing)
        def _(event) -> None:
            self.q_sel = (self.q_sel + 1) % self._picker_rows()
            self.app.invalidate()

        for _i in range(9):

            @kb.add(str(_i + 1), filter=choosing)
            def _(event, idx=_i) -> None:
                if idx < self._picker_rows():
                    self.q_sel = idx
                    self.app.invalidate()

        @kb.add("escape", filter=Condition(lambda: self.q_active))
        def _(event) -> None:
            self._answer(None)

        @kb.add(
            "escape",
            filter=Condition(
                lambda: (
                    self.busy
                    and not self.q_active
                    and not self.mp_active
                    and not self.fp_active
                    and not self.tp_active
                )
            ),
        )
        def _(event) -> None:  # Esc during generation → stop + restore the request
            self._cancel_generation()

        @kb.add("enter", filter=modeling)
        def _(event) -> None:
            self._mp_pick()

        @kb.add("up", filter=modeling)
        def _(event) -> None:
            self._mp_move(-1)

        @kb.add("down", filter=modeling)
        def _(event) -> None:
            self._mp_move(1)

        @kb.add("escape", filter=modeling)
        def _(event) -> None:
            self._mp_cancel()

        @kb.add("enter", filter=filing)
        def _(event) -> None:
            self._fp_pick()

        @kb.add("up", filter=filing)
        def _(event) -> None:
            self._fp_move(-1)

        @kb.add("down", filter=filing)
        def _(event) -> None:
            self._fp_move(1)

        @kb.add("escape", filter=filing)
        def _(event) -> None:
            self._fp_cancel()

        for _i in range(9):

            @kb.add(str(_i + 1), filter=filing)
            def _(event, idx=_i) -> None:
                self._fp_select_row(idx)

        @kb.add("enter", filter=theming)
        def _(event) -> None:
            self._tp_pick()

        @kb.add("up", filter=theming)
        def _(event) -> None:
            self._tp_move(-1)

        @kb.add("down", filter=theming)
        def _(event) -> None:
            self._tp_move(1)

        @kb.add("escape", filter=theming)
        def _(event) -> None:
            self._tp_cancel()

        for _i in range(9):

            @kb.add(str(_i + 1), filter=theming)
            def _(event, idx=_i) -> None:
                self._tp_select_row(idx)

        @kb.add("s-tab", filter=normal)
        def _(event) -> None:
            self.state.mode = self._next_mode(self.state.mode)
            self.app.invalidate()

        @kb.add("c-o")
        def _(event) -> None:
            self.meta_expanded = not self.meta_expanded
            self.app.invalidate()

        # Ctrl+I IS Tab in prompt_toolkit (same key code) — gate the inspector
        # toggle so it only fires when no completion menu is open. Otherwise it
        # shadows the default Tab binding that cycles slash-command completions
        # (docs/en/reference/tui.md), since this Application's own bindings take
        # priority over prompt_toolkit's merged defaults. (M187 regression fix.)
        @kb.add("c-i", filter=Condition(lambda: self.input.buffer.complete_state is None))
        def _(event) -> None:
            self.meta_expanded = not self.meta_expanded
            self.app.invalidate()

        # $EDITOR compose (M187 Task 7): prompt_toolkit ships an emacs
        # `c-x c-e` -> `Buffer.open_in_editor()` binding via
        # `load_open_in_editor_bindings()`, but this Application's default
        # bindings come from `load_key_bindings()` (key_binding/defaults.py),
        # which does NOT merge that one in — so `c-x c-e` does nothing here
        # out of the box. We wire it ourselves, straight onto the input
        # buffer, rather than merging in the stock bindings (keeps one
        # KeyBindings object to reason about). No collision: neither the
        # emacs `c-x` prefix map (`c-u`/`r y`/`(`/`)`/`e`/`c-x` as the second
        # key — see `key_binding/bindings/emacs.py`) nor any binding of ours
        # uses "c-e" as the second key of a `c-x` chord. Same no-TTY guard as
        # `_ask`/`_confirm_critical` so a headless run/test degrades to a
        # no-op instead of hanging on a real editor subprocess spawn.
        @kb.add("c-x", "c-e", filter=normal)
        def _(event) -> None:
            if not sys.stdin.isatty():
                return
            self.input.buffer.open_in_editor()

        # Image paste (M187 Task 7). Deliberately NOT Ctrl+G — the old
        # Textual composer's binding — because Ctrl+G is prompt_toolkit's
        # DEFAULT abort/keyboard-quit (`c-g` in both `basic.py` and
        # `emacs.py`: cancel-selection / abort-incremental-search). Left
        # unbound here so that default keeps working. Ctrl+V has no default
        # binding that matters in this Application: `basic.py`'s `c-v` is a
        # no-op placeholder, and the emacs `c-v` -> scroll-page-down only
        # activates under `enable_page_navigation_bindings`, which is gated
        # on `full_screen` — this Application passes `full_screen=False`.
        @kb.add("c-v", filter=normal)
        def _(event) -> None:
            self._paste_clipboard()

        @kb.add("c-d")
        def _(event) -> None:
            event.app.exit()

        @kb.add("c-c")
        def _(event) -> None:
            self._on_ctrl_c(event)

        return kb

    def _on_enter(self) -> None:
        raw = self.input.text
        text = raw.strip()
        self.input.text = ""
        if not text:
            self._hist_pos = None
            return  # ignore empty input
        self._record_history(raw)
        self._spawn(self._dispatch(text))

    # --- input history (explicit; the Buffer's async FileHistory didn't resync
    # a just-submitted command in this embedded Application) ---

    def _record_history(self, text: str) -> None:
        """Append a submitted command to the in-memory history and persist it to
        the shared `repl_history` file. Skips a consecutive duplicate. Resets the
        recall cursor so the next Up starts from the newest entry."""
        text = text.rstrip("\n")
        if text and (not self._hist or self._hist[-1] != text):
            self._hist.append(text)
            import contextlib

            with contextlib.suppress(Exception):
                self._hist_store.store_string(text)  # cross-run persistence
        self._hist_pos = None

    def _set_input(self, text: str) -> None:
        self.input.text = text
        self.input.buffer.cursor_position = len(text)  # cursor at end of recall

    def _history_up(self) -> None:
        # Multiline: move the cursor up within the text unless already on the
        # first row — only then recall an older command.
        doc = self.input.buffer.document
        if doc.cursor_position_row > 0:
            self.input.buffer.cursor_up()
            return
        if not self._hist:
            return
        if self._hist_pos is None:  # starting recall — stash the draft line
            self._hist_draft = self.input.text
            self._hist_pos = len(self._hist)
        if self._hist_pos > 0:
            self._hist_pos -= 1
            self._set_input(self._hist[self._hist_pos])

    def _history_down(self) -> None:
        doc = self.input.buffer.document
        if doc.cursor_position_row < doc.line_count - 1:
            self.input.buffer.cursor_down()
            return
        if self._hist_pos is None:
            return
        self._hist_pos += 1
        if self._hist_pos >= len(self._hist):  # past the newest → restore draft
            self._hist_pos = None
            self._set_input(self._hist_draft)
        else:
            self._set_input(self._hist[self._hist_pos])

    def _on_ctrl_c(self, event) -> None:
        if self.tp_active:
            self._tp_cancel()  # cancel the /theme picker
            return
        if self.fp_active:
            self._fp_cancel()  # cancel the @ file picker
            return
        if self.mp_active:
            self._mp_cancel()  # cancel the /model picker
            return
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

    def _cancel_generation(self) -> None:
        """Esc while a turn runs: stop it *now*. Cancelling the token both
        unwinds the agent loop (at its next ~100ms check) and instantly gates
        the output callbacks (see `_make_turn_callbacks` `stop_check`), so
        visible generation halts immediately. The request text is dropped back
        into the input box for editing ONLY when nothing was generated yet;
        once the answer has started streaming, Esc is a plain stop. Also clears
        the queue so Esc fully stops (not just the current turn)."""
        if self.cancel_token is not None:
            self.cancel_token.cancel()  # stop the turn + gate its output at once
        self.queue.clear()  # a full stop — don't run queued follow-ups
        if self.stream_chars == 0 and self._last_submitted:
            self._set_input(self._last_submitted)  # restore only before first output
        self.app.invalidate()

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
            parts = text.split()
            # /model with no id (or `refresh`) → the inline filterable picker,
            # driven inside this Application. /model <id> still sets directly
            # via the shared slash handler below. Never while `busy`: a
            # mid-turn `_ask`/`_permission_prompt` can flip `q_active` on top
            # of an already-open picker, colliding two filter states at once.
            # NOTE: fall through to `_slash` below rather than queuing — the
            # queue drain in `_run_chain` feeds straight into `_blocking_turn`
            # with no re-dispatch, so a queued "/model" would be sent to the
            # LLM as a chat prompt once the turn ends. Falling through runs
            # the same immediate path every other slash command already takes
            # during `busy` (here, `_handle_slash` prints the static model
            # list instead of opening the interactive picker).
            if (
                parts
                and parts[0].lower() == "/model"
                and (len(parts) == 1 or parts[1].lower() == "refresh")
                and not self.busy
            ):
                self._echo_user(text)
                self._open_model_picker(refresh=len(parts) > 1)
                return
            # /theme with no name → the inline filterable picker, mirroring
            # /model above. /theme <name> still sets directly via the shared
            # slash handler below (it goes through the registry's `_theme`,
            # which persists — `_slash` then notices `state.theme_name`
            # changed and re-applies the live restyle). Same busy-guard (and
            # same reason) as /model above.
            if parts and parts[0].lower() == "/theme" and len(parts) == 1 and not self.busy:
                self._echo_user(text)
                self._open_theme_picker()
                return
            await self._slash(text)
            return
        if self.busy:
            self.queue.append(text)
            self.console.print(f"  ⋅ queued: {text}", style=self.theme.muted, markup=False)
            return
        await self._run_chain(text)

    async def _slash(self, text: str) -> None:
        self._echo_user(text)
        prev_theme = self.state.theme_name
        box: dict = {}

        def _do() -> None:
            box["res"] = _handle_slash(
                text, self.registry, self.state, self.project, self.store, self.console, self.errors
            )

        # run_in_terminal: /sessions may read input (rich.Prompt.ask), which
        # needs the terminal handed back from the app.
        await self._in_terminal(_do)
        # `/theme <name>` sets state.theme_name via the registry's `_theme`
        # handler (already persisted there) — restyle the running app here so
        # the direct-set path applies live too, same as picking from `_tp_pick`.
        if self.state.theme_name != prev_theme:
            self._apply_theme_live()
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
                self.tool_activity = {}
                self.turn_start = time.monotonic()
                self._last_submitted = text  # remember it so Esc can restore it
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
                self.turn_elapsed = time.monotonic() - self.turn_start  # freeze the timer
                _update_state_after_turn(self.state, result)
                # M191: run the learning loop (insight extraction + curation)
                # on the completed turn, same as `veles run`. Skips None/cancel.
                _run_repl_post_turn_hooks(self.args, self.project, result)
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
            self.console,
            self.theme,
            self.errors,
            on_meta=self._push_meta,
            stop_check=lambda: self.cancel_token is not None and self.cancel_token.cancelled,
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
    from veles.cli.repl.slash import build_default_registry

    runtime = _build_runtime(args, project)
    if runtime is None:
        return 2
    state, factory, store, subagent_factory = runtime
    registry = build_default_registry(project=project)
    console = _console()
    theme = _resolve_theme(state)
    errors: list[str] = []

    try:
        _banner(console, args.provider, args.model, state.mode, theme)
        if state.session_id:  # -c / --resume → show the conversation we continue
            _print_resume_recap(console, theme, store, state.session_id)
        # Default: the inline Application — a settled bottom status bar (mode +
        # token/cache stats), a live "working…" HUD during generation (Ctrl+O
        # expands tool/mode activity), and the in-app ask_user picker. It pins
        # the status bar correctly over long scrolling output (rich.Live can't).
        # The blocking-prompt loop is a fallback via VELES_REPL_SIMPLE=1 for
        # terminals where the Application misbehaves.
        if os.environ.get("VELES_REPL_SIMPLE"):
            _run_simple_repl(
                args,
                project,
                state,
                factory,
                store,
                registry,
                console,
                theme,
                errors,
                subagent_factory=subagent_factory,
            )
        else:
            _ReplApp(
                args,
                project,
                state,
                factory,
                store,
                registry,
                console,
                theme,
                errors,
                subagent_factory=subagent_factory,
            ).run()
    finally:
        store.close()
    return 0
