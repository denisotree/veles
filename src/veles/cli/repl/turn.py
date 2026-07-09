"""Turn execution + rendering for the inline REPL.

The per-turn machinery: the behavioural system-prompt block, the turn
system-prompt assembler, the post-turn learning-loop hooks, the streaming
turn callbacks (block-by-block Markdown rendering + edit diffs), state
carry-forward, the fallback simple-loop turn driver, and the `/command`
dispatcher. `TurnMixin` (the `_ReplApp` turn methods) is appended in
Phase 3. Cross-module references to `terminal`/`pickers.helpers` are
one-directional (both are lower leaves); `_handle_slash` imports them at
module scope.
"""

from __future__ import annotations

import argparse
import asyncio
import contextvars
import time

from veles.cli.repl.pickers.helpers import (
    _pick_session,
    _print_model_list,
    _print_theme_list,
)
from veles.cli.repl.terminal import _print_repl_help
from veles.core.project import Project

# Injected into the REPL's system prompt for normal auto/writing turns (NOT
# goal mode, which drives its own one-step-per-turn phase prompts). Three levers:
# persistence (finish the whole job), acting-now (the failure mode where a model
# announces a plan / "I'll report back" and stops without doing the work — the
# turn ends the instant it returns no tool calls, so there IS no "later"), and
# routing genuine decisions through the `ask_user` picker instead of prose.
_REPL_BEHAVIOUR_BLOCK = (
    "## Working through a task\n"
    "When the user asks you to carry out work — especially across MANY items "
    '("loop through all pages", "fix everything", "review each file") — do the '
    "WHOLE task in this turn. Work item by item: read it, make the change, move "
    "to the next, until every item is handled. You have many tool calls per turn "
    "— use them. Do NOT stop after one or two items to summarise and ask whether "
    "to continue; that needlessly interrupts the work. Stop only when the task "
    "is genuinely complete or you hit a real blocker.\n\n"
    "## Break big work into delegated subtasks\n"
    "For a non-trivial, multi-part task, prefer to DECOMPOSE it and hand each "
    "small, self-contained piece to a focused worker with the `delegate` tool "
    "instead of doing everything yourself in one long context. Give each worker "
    'ONLY the tools it needs (e.g. `delegate("rewrite file X as a wiki page and '
    'link it", tools=["read_file", "wiki_write_page", "wiki_search", '
    '"move_file"], context="target structure: …")`), read its report, and '
    "either accept the result and move on or delegate a correction. Do the small "
    "trivial steps yourself; delegate the repeated or heavy ones. You remain the "
    "coordinator — you decide the decomposition and integrate the results.\n\n"
    "## Act now — there is no 'later'\n"
    "This reply is the ONLY place work happens. There is no background, no async, "
    "no next turn you control — the moment you stop making tool calls, the turn "
    'ends. So anything you announce — "I\'ll create these files", "приступаю", '
    '"working on it", "I\'ll report back in a few minutes" — you must actually '
    "carry out with tool calls in THIS same reply, before you stop. Prose, plans "
    'and parenthetical asides like "(creating the pages)" are NOT actions; only '
    "tool calls (`write_file`, `edit_file`, …) change anything. Never end a reply "
    "having only described work you did not perform. If you named files to create "
    "or edit, create or edit them now, in this reply. If you are not going to do "
    "something, do not claim you are.\n\n"
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


def _repl_turn_system_prompt(
    args: argparse.Namespace,
    project: Project,
    *,
    mode,
    query: str | None,
    extra_system: str | None,
) -> str | None:
    """Assemble one REPL turn's system prompt.

    M191: `query` (the raw user prompt) drives `<memory-context>` recall +
    `<relevant-files>`. Before M191 the REPL passed an empty query, so the
    flagship UX never recalled project memory. An empty query still yields no
    recall (matches `veles run` with no prompt), so batch/mode-less callers
    keep the cache-stable stable-only prefix.
    """
    from veles.cli import build_run_system_prompt

    sys_chunks: list[str] = []
    base = build_run_system_prompt(
        project,
        prompt=query or "",
        include_agents_md=not getattr(args, "no_agents_md", False),
        include_index=not getattr(args, "no_index", False),
    )
    if base:
        sys_chunks.append(base)
    if mode.system_block.strip():
        sys_chunks.append(mode.system_block.strip())
    if extra_system and extra_system.strip():
        # A phase prompt is driving this turn (goal mode's own FSM, which is
        # deliberately one-step-per-turn) — don't inject the persistence block,
        # it would contradict "run the step, then STOP".
        sys_chunks.append(extra_system.strip())
    else:
        sys_chunks.append(_REPL_BEHAVIOUR_BLOCK)
    return "\n\n".join(sys_chunks) if sys_chunks else None


def _run_repl_post_turn_hooks(args: argparse.Namespace, project: Project, result) -> None:
    """M191: after each REPL turn, run the same learning-loop upkeep `veles run`
    fires — insight extraction on the completed turn + post-turn curation (the
    light dream pass rides inside the curator). Before M191 the flagship REPL
    ran none of this, so raw turns were stored but never distilled into recall.

    Skipped entirely when the turn produced no result (error) or was cancelled
    (Ctrl+C) — there is nothing to extract, and memory upkeep must never distil
    a half-finished turn.
    """
    if result is None or getattr(result, "stopped_reason", "") == "cancelled":
        return
    from veles.cli import _maybe_run_insight_extractor, _maybe_run_post_turn_curator

    _maybe_run_insight_extractor(args, project, result.history, result.session_id)
    _maybe_run_post_turn_curator(args, project)


def _make_turn_callbacks(console, theme, errors: list[str], on_meta=None, stop_check=None):
    """Build (post, on_text, on_event) for a `ModeContext`, plus a holder for
    the final `RunResult`.

    These **stream by block**: answer tokens accumulate in a buffer, and each
    completed Markdown block (paragraph, list, table, fenced code) is rendered
    formatted as soon as its terminating blank line arrives — progressive AND
    formatted. `flush()` renders the trailing block at end of turn. Under the
    Application's `patch_stdout`, writes from the executor thread appear above
    the live input box.

    `on_meta(kind, text, *, tool_call_id="", error=None)` (optional) is the
    live-generation HUD sink: it receives ``("stream", chunk)`` for every
    answer chunk (so the app can show a running token estimate), ``("mode",
    text)`` on a mode switch, ``("tool", text, tool_call_id=...)`` on each tool
    call (the id starts the inspector's per-tool timer/status row), and
    ``("tool_result", "", tool_call_id=..., error=...)`` when that call's
    result comes back — the inspector uses it to mark the row done/failed and
    freeze its duration. When it's None (the fallback simple loop) mode
    switches print inline instead.

    Returns ``(post, on_text, on_event, holder, flush)``.
    """
    from veles.core.agent_events import AgentError, ChatDelta, SystemLine, TurnDone

    holder: dict[str, object] = {}
    buf = [""]  # mutable string cell shared across chunks

    def _emit(chunk: str) -> None:
        # Esc-to-stop: once the turn is cancelled, drop further tokens at the
        # source so visible output halts instantly (the cooperative cancel in
        # the agent loop only unwinds at the next ~100ms check).
        if stop_check is not None and stop_check():
            return
        if on_meta is not None:
            on_meta("stream", chunk)
        buf[0] += chunk
        blocks, buf[0] = _split_blocks(buf[0])
        for block in blocks:
            if block.strip():
                _render_answer(console, block)

    def flush() -> None:
        if stop_check is not None and stop_check():
            buf[0] = ""
            return
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
        etype = getattr(event, "type", "")
        if etype == "round_usage":
            # Real cumulative output tokens for the HUD — a tool-call-only
            # turn streams no text, so the chars/4 estimate alone reads ≈0.
            if on_meta is not None:
                on_meta("usage", str(getattr(event, "cumulative_completion", 0)))
            return
        if etype == "tool_result":
            # Completion signal for the inspector's per-tool status/duration —
            # correlated with the tool_call above via tool_call_id. Carries no
            # display text of its own (the "tool" line was already pushed).
            if on_meta is not None:
                on_meta(
                    "tool_result",
                    "",
                    tool_call_id=getattr(event, "tool_call_id", "") or "",
                    error=getattr(event, "error", None),
                )
            return
        if etype != "tool_call":
            return
        name = getattr(event, "name", "")
        args = getattr(event, "arguments", {}) or {}
        if on_meta is not None:
            label = f"{name} {args.get('path', '')}".strip()
            on_meta("tool", label, tool_call_id=getattr(event, "tool_call_id", "") or "")
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


def _handle_slash(
    line: str, registry, state, project, store, console, errors: list[str]
) -> tuple[bool, str | None]:
    """Dispatch a `/command`. Returns ``(should_quit, submit_prompt)``."""
    from veles.cli.repl.slash import SlashContext

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
    elif result.open_picker in ("models", "models:refresh"):
        _print_model_list(
            console,
            state.provider_name,
            state.model,
            refresh=result.open_picker.endswith("refresh"),
        )
    elif result.open_picker == "themes":
        _print_theme_list(console, state.theme_name)
    elif result.open_picker == "daemon":
        # The daemon control panel is a standalone Textual surface (`veles
        # daemon`), not a modal nested inside this REPL — no picker to open
        # here, so point at the real surface instead of the generic (and
        # nonsensical, for `/daemon`) "set directly" hint below.
        console.print(
            "  [dim]the daemon control panel is a separate surface — "
            "run `veles daemon` in your shell[/dim]"
        )
    elif result.open_picker:
        console.print(f"  [dim]{result.open_picker}: set directly, e.g. /model <id>[/dim]")
    return result.quit, result.submit_prompt


class TurnMixin:
    """Turn dispatch + execution for the inline `_ReplApp`.

    `_dispatch` routes a submitted line (slash vs prompt vs queue-while-busy);
    `_slash` runs a `/command` (handing the terminal back for pickers that read
    input); `_run_chain` drives the busy loop that runs each queued turn in the
    executor inside a fresh copy of the captured parent context; `_blocking_turn`
    is the executor-thread body that streams the answer via the turn callbacks.
    All state lives on `_ReplApp`; helper functions come from this module.
    """

    def _spawn(self, coro) -> None:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    @property
    def upkeep_busy(self) -> bool:
        """True while M191 post-turn memory upkeep runs on the worker."""
        return bool(self._upkeep_futures)

    def _submit_upkeep(self, result) -> None:
        """Schedule the M191 post-turn hooks (insight extraction + curation) on
        the dedicated single upkeep worker. The hooks make their own LLM calls
        — inline on the event-loop thread they froze the whole UI for seconds
        after the answer finished (live 2026-07-09). One worker = passes from
        back-to-back turns queue instead of stacking. Runs in a fresh copy of
        the captured parent context, same as the turn itself (`run_in_executor`
        / plain threads don't propagate ContextVars — without it the hooks
        would lose the active project)."""
        ctx = self._parent_ctx.run(contextvars.copy_context)

        def _job() -> None:
            ctx.run(_run_repl_post_turn_hooks, self.args, self.project, result)

        fut = self._upkeep_pool.submit(_job)
        self._upkeep_futures.add(fut)
        self._invalidate_threadsafe()  # show the HUD upkeep chip

        def _done(f) -> None:
            self._upkeep_futures.discard(f)
            self._invalidate_threadsafe()  # drop the chip

        fut.add_done_callback(_done)

    def _note_pending_upkeep(self) -> None:
        """On quit with upkeep still in flight, say so: the interpreter waits
        for the worker thread at exit, and a silent multi-second pause after
        Ctrl+D reads as a hang."""
        if self.upkeep_busy:
            self.console.print("  ⋅ finishing memory upkeep…", style=self.theme.muted, markup=False)

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
                self.turn_tokens_out = 0
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
                reason = (
                    getattr(result, "stopped_reason", "error") if result is not None else "error"
                )
                self.last_stopped_reason = reason
                if reason == "cancelled":
                    self.console.print("  ⋅ cancelled", style=self.theme.muted, markup=False)
                elif reason == "max_iterations":
                    # The turn ran out of steps — it did NOT finish the task. Say
                    # so plainly (the HUD marker alone reads like success), and
                    # point at the ways to actually complete a big job.
                    self.console.print(
                        f"  ⚠ stopped at the {self.args.max_iterations}-step limit — the task is "
                        "NOT finished. Continue with another message, raise --max-iterations, or "
                        "for a whole-folder migration use `veles add <dir> --recursive`.",
                        style=self.theme.error,
                        markup=False,
                    )
                elif reason == "budget_exhausted":
                    self.console.print(
                        "  ⚠ stopped — token budget exhausted; the task is not finished.",
                        style=self.theme.error,
                        markup=False,
                    )
                self.console.print()  # trailing blank after the streamed answer
                self.turn_elapsed = time.monotonic() - self.turn_start  # freeze the timer
                _update_state_after_turn(self.state, result)
                # M191: run the learning loop (insight extraction + curation)
                # on the completed turn, same as `veles run`. Skips None/cancel.
                # In the background — these hooks make their own LLM calls, and
                # running them inline here (the event-loop thread) froze the
                # whole UI for seconds between "answer done" and "✓ done"
                # (live 2026-07-09).
                self._submit_upkeep(result)
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
