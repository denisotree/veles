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

from veles.cli.repl.history import HistoryMixin
from veles.cli.repl.hud import HudMixin
from veles.cli.repl.keys import KeysMixin
from veles.cli.repl.pickers.file import FilePickerMixin
from veles.cli.repl.pickers.helpers import (  # noqa: F401  (_print_model_list is a test shim)
    _at_trigger_boundary,
    _filter_files,
    _filter_models,
    _new_paste_filename,
    _print_model_list,
)
from veles.cli.repl.pickers.model import ModelPickerMixin
from veles.cli.repl.pickers.theme import ThemePickerMixin
from veles.cli.repl.prompts import PromptsMixin
from veles.cli.repl.runtime import _build_runtime
from veles.cli.repl.simple import _ask_repl, _run_simple_repl  # noqa: F401  (_ask_repl is a shim)
from veles.cli.repl.terminal import (  # noqa: F401  (_settled_status is a test shim)
    _CTRL_C_EXIT_WINDOW_S,
    _KITTY_ENABLE,
    _banner,
    _console,
    _kitty_disable_keyboard,
    _print_resume_recap,
    _register_kitty_sequences,
    _resolve_theme,
    _settled_status,
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


class _ReplApp(
    KeysMixin,
    HistoryMixin,
    PromptsMixin,
    HudMixin,
    ModelPickerMixin,
    ThemePickerMixin,
    FilePickerMixin,
):
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
