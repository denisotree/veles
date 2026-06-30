"""`veles repl` — inline streaming REPL (the "act like `cat`" interface).

Why this exists (research in M185): the full-screen `veles tui` runs in the
terminal's *alternate screen buffer* and must capture the mouse to scroll,
which disables the terminal's native text selection and makes the terminal
eat ⌘C. There is no way to have app-managed wheel-scroll AND native
selection/copy at once in a full-screen TUI.

This REPL takes the opposite approach: it renders to the **normal** screen
buffer and never enables mouse reporting, so the terminal owns scrollback,
text selection and clipboard copy (⌘C on macOS / Ctrl+Shift+C on Linux)
natively. Assistant output streams straight to stdout; the input line is
drawn inline by prompt_toolkit, which does NOT switch to the alternate
screen or capture the mouse.

It reuses the framework-agnostic core the Textual TUI already exposes —
`AppState`, the `slash` command registry, and the `core.modes` FSM
(auto/planning/writing/goal). The only thing that changes is the
presentation layer: the Textual app + bridge + widgets are replaced by
print-based callbacks. The old `veles tui` is untouched.

Migration status: Phase 1 — slash commands, modes, streaming, status line.
Phase 2 (pickers, markdown render) and Phase 3 (@file refs, mid-turn
cancel, /errors, queue) follow.
"""

from __future__ import annotations

import argparse
import sys

from veles.core.project import Project

# ---- ANSI helpers (selectable plain text; the terminal owns colour) ----

_DIM = "\x1b[2m"
_RED = "\x1b[31m"
_RESET = "\x1b[0m"


def _build_runtime(args: argparse.Namespace, project: Project):
    """Resolve provider/model, gate the API key, and build the per-turn Agent
    factory + AppState + store — a faithful mirror of `tui.run_tui`'s setup.

    Returns ``(state, factory, store)`` or ``None`` when the key gate fails
    (the caller returns exit code 2).

    NOTE (dedup): this intentionally duplicates `run_tui`'s factory. Once the
    REPL is the canonical interactive surface, both should share one builder
    and the Textual copy should go.
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
        sys_chunks: list[str] = []
        if state.session_id is None:
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

    state = AppState(
        session_id=getattr(args, "resume", None),
        provider_name=args.provider,
        model=args.model,
    )
    return state, factory, store


def _make_turn_callbacks(state):
    """Build the (post, on_text, on_event) callbacks a `ModeContext` needs,
    plus a holder dict the caller reads the final `RunResult` back from.

    The modes never import Textual — they only call these — so the same FSM
    that drives the Textual TUI drives the REPL, just printing instead of
    posting to widgets.
    """
    from veles.tui.messages import AgentError, ChatDelta, SystemLine, TurnDone

    holder: dict[str, object] = {}

    def post(msg) -> None:
        if isinstance(msg, TurnDone):
            holder["result"] = msg.result
        elif isinstance(msg, SystemLine):
            print(f"{_DIM}{msg.text}{_RESET}")
        elif isinstance(msg, ChatDelta):
            sys.stdout.write(msg.text)
            sys.stdout.flush()
        elif isinstance(msg, AgentError):
            print(f"\n{_RED}error:{_RESET} {msg.exc}", file=sys.stderr)

    def on_text(text: str) -> None:
        sys.stdout.write(text)
        sys.stdout.flush()

    def on_event(_event) -> None:
        # Phase 3: collect typed errors for a `/errors` command.
        return None

    return post, on_text, on_event, holder


def _update_state_after_turn(state, result) -> None:
    """Carry session id, last reply and token totals forward (mirrors
    `TuiApp.on_turn_done`)."""
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


def _run_mode_turn(state, project, factory, line: str):
    """Drive one user turn through the active mode's FSM and return the
    `RunResult` (or None if the mode posted no TurnDone)."""
    from veles.core.modes import ModeContext, get_mode

    post, on_text, on_event, holder = _make_turn_callbacks(state)
    ctx = ModeContext(
        state=state,
        project=project,
        factory=factory,
        post=post,
        on_text=on_text,
        on_event=on_event,
    )
    get_mode(state.mode).run_turn(line, ctx)
    return holder.get("result")


def _handle_slash(line: str, registry, state, project, store) -> tuple[bool, str | None]:
    """Dispatch a `/command` through the shared slash registry.

    Returns ``(should_quit, submit_prompt)`` — ``submit_prompt`` is a prompt a
    command asked to run as an agent turn (e.g. `/wiki query`).
    """
    from veles.tui.slash import SlashContext

    ctx = SlashContext(state=state, project=project, store=store)
    result = registry.dispatch(line, ctx)
    if result is None:
        print(f"unknown command: {line.split()[0]} (try /help)", file=sys.stderr)
        return False, None
    if result.text:
        stream = sys.stderr if result.is_error else sys.stdout
        print(result.text, file=stream)
    if result.clear_chat:
        # Start a fresh session; never wipe the terminal (that would drop the
        # scrollback the whole inline model exists to preserve).
        state.session_id = None
        state.last_assistant_text = None
    if result.open_picker:
        print(
            f"{_DIM}(picker '{result.open_picker}' is not in the repl yet — Phase 2){_RESET}",
            file=sys.stderr,
        )
    return result.quit, result.submit_prompt


def _make_prompt_session(project: Project, registry, state):
    """prompt_toolkit session: history under `.veles/`, slash autocompletion
    from the live registry, a status bottom-toolbar, and Shift+Tab to cycle
    the mode. Plain prompt mode — no alternate screen, no mouse capture."""
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.key_binding import KeyBindings

    from veles.core.modes import next_mode

    class _SlashCompleter(Completer):
        def get_completions(self, document, complete_event):
            text = document.text_before_cursor
            if not text.startswith("/") or " " in text:
                return
            for name in registry.names():
                if name.startswith(text):
                    yield Completion(name, start_position=-len(text))

    def _toolbar():
        sid = state.session_id or "new"
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
    from veles.tui.slash import build_default_registry

    runtime = _build_runtime(args, project)
    if runtime is None:
        return 2
    state, factory, store = runtime
    registry = build_default_registry(project=project)

    try:
        print(f"veles repl · {args.provider}:{args.model} · /help · Ctrl+D to exit")
        prompt_session = _make_prompt_session(project, registry, state)

        while True:
            try:
                line = prompt_session.prompt("you> ")
            except KeyboardInterrupt:
                continue  # Ctrl+C cancels the current line (REPL idiom).
            except EOFError:
                break  # Ctrl+D exits.

            line = line.strip()
            if not line:
                continue

            if line.startswith("/"):
                should_quit, submit = _handle_slash(line, registry, state, project, store)
                if should_quit:
                    break
                if not submit:
                    continue
                line = submit  # fall through and run the command's prompt

            print()
            try:
                result = _run_mode_turn(state, project, factory, line)
            except KeyboardInterrupt:
                print("\n<interrupted>", file=sys.stderr)
                continue
            except Exception as exc:
                print(f"\n{_RED}error:{_RESET} {exc}", file=sys.stderr)
                continue
            _update_state_after_turn(state, result)
            sys.stdout.write("\n")
            sys.stdout.flush()
    finally:
        store.close()
    print("bye")
    return 0
