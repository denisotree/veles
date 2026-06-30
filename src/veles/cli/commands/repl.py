"""`veles repl` (M186 prototype) — streaming **inline** REPL.

Why this exists (research in M185): the full-screen `veles tui` runs in the
terminal's *alternate screen buffer* and must capture the mouse to scroll,
which disables the terminal's native text selection and makes the terminal
eat ⌘C. There is no way to have app-managed wheel-scroll AND native
selection/copy at once in a full-screen TUI.

This prototype takes the opposite, "act like `cat`" approach: it renders to
the **normal** screen buffer and never enables mouse reporting. Assistant
output is streamed straight to stdout (lines land in the terminal's own
scrollback); the input line is drawn inline by prompt_toolkit, which does
NOT switch to the alternate screen or capture the mouse. The result:

  * mouse-wheel scrolling      → the terminal's native scrollback
  * mouse text selection       → native
  * copy ⌘C (macOS) / Ctrl+Shift+C (Linux) → the terminal's native copy

…all work out of the box, because Veles never takes the screen or the
mouse away from the terminal.

Scope (prototype): single streaming session, history + slash autocomplete,
a handful of local slash commands. The rich full-screen extras (status
panel, inspector, pickers) are intentionally absent — pickers would later
reuse the `mouse=False` full-screen pattern that `veles daemon` already
ships. The agent build mirrors `cmd_run` exactly, so memory/skills/routing
behave identically.
"""

from __future__ import annotations

import argparse
import sys

from veles.core.project import Project

# Local slash commands the prototype understands. Production would reuse the
# `tui/slash` registry once it's decoupled from the Textual app/state.
_SLASH: dict[str, str] = {
    "/help": "show this help",
    "/clear": "clear the screen",
    "/quit": "exit the REPL",
    "/exit": "exit the REPL",
}


def _dispatch_slash(line: str) -> str:
    """Classify an input line.

    Returns one of: ``"run"`` (not a slash — send to the agent), ``"quit"``,
    ``"clear"``, ``"help"``, or ``"unknown"`` (an unrecognised `/command`).
    """
    if not line.startswith("/"):
        return "run"
    cmd = line.split()[0].lower()
    if cmd in ("/quit", "/exit"):
        return "quit"
    if cmd == "/clear":
        return "clear"
    if cmd == "/help":
        return "help"
    return "unknown"


def _print_help() -> None:
    print("\nslash commands:")
    for cmd, desc in _SLASH.items():
        print(f"  {cmd:<8} {desc}")
    print("  Ctrl+D    exit · Ctrl+C cancel the current line\n")
    print(
        "copy: select with the mouse and press ⌘C (macOS) / Ctrl+Shift+C (Linux) — "
        "native terminal copy, no special mode.\n"
    )


def _run_turn(agent, line: str, args: argparse.Namespace) -> None:
    """Stream one agent turn to stdout. Reuses the exact `cmd_run` streaming
    path so output, budget and trust handling are identical."""
    from veles.cli import _run_agent_streaming_aware
    from veles.core.provider import ProviderError

    print()
    sys.stdout.write("assistant> ")
    sys.stdout.flush()
    try:
        _run_agent_streaming_aware(agent, line, args, emit_output=True)
    except ProviderError as exc:
        # A provider timeout / 5xx is a clean operational failure (M132b),
        # not a crash — keep the REPL alive.
        print(f"\nerror: {exc}", file=sys.stderr)
    except KeyboardInterrupt:
        # Ctrl+C mid-stream cancels just this turn.
        print("\n<interrupted>", file=sys.stderr)
    print()


def _make_prompt_session(project: Project):
    """Build a prompt_toolkit session: history persisted under `.veles/`,
    slash-command autocompletion. Plain prompt mode — no alternate screen,
    no mouse capture (both are prompt_toolkit defaults here)."""
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.history import FileHistory

    class _SlashCompleter(Completer):
        def get_completions(self, document, complete_event):
            text = document.text_before_cursor
            if not text.startswith("/") or " " in text:
                return
            for cmd in _SLASH:
                if cmd.startswith(text):
                    yield Completion(cmd, start_position=-len(text))

    hist_path = project.state_dir / "repl_history"
    return PromptSession(
        history=FileHistory(str(hist_path)),
        completer=_SlashCompleter(),
        complete_while_typing=True,
    )


def cmd_repl(args: argparse.Namespace, project: Project) -> int:
    from veles.cli import (
        _PROVIDER_API_KEY_ENVS,
        _RUN_TOOLS,
        _build_run_system_prompt,
        _ensure_api_key,
        _touch_active_project,
        _warn_if_agents_md_invalid,
        build_command_agent,
    )
    from veles.core.memory import SessionStore
    from veles.core.model_resolver import (
        ConfigurationError,
        ensure_model_configured,
        resolve_effective_model,
        resolve_effective_provider,
    )

    # Mirror cmd_run's resolution + key gate.
    args.provider = resolve_effective_provider(args, project)
    try:
        args.model = ensure_model_configured(resolve_effective_model(args, project))
    except ConfigurationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.provider in _PROVIDER_API_KEY_ENVS and not _ensure_api_key(args.provider):
        return 2

    # Force streaming so the answer lands in the terminal scrollback live —
    # the whole point of the inline model.
    args.stream = True
    _touch_active_project(project)
    _warn_if_agents_md_invalid(project)

    store = SessionStore(project.memory_db_path)
    try:
        session_id = getattr(args, "resume", None)
        system_prompt = None if session_id else _build_run_system_prompt(args, project)
        # One agent for the whole session: history is store-backed
        # (`_bootstrap_history` reloads by session_id each turn), so repeated
        # `.run()` calls continue the same conversation.
        agent = build_command_agent(
            args,
            project,
            tools=_RUN_TOOLS,
            system_prompt=system_prompt,
            check_api_key=False,
            with_compressor=True,
            store=store,
            session_id=session_id,
        )
        if agent is None:
            return 2

        print(f"veles repl · {args.provider}:{args.model} · /help · Ctrl+D to exit")
        prompt_session = _make_prompt_session(project)

        def _toolbar():
            sid = agent._session_id or "new"
            return f" {args.provider}:{args.model} · session {sid} · /help · Ctrl+D exit "

        while True:
            try:
                line = prompt_session.prompt("you> ", bottom_toolbar=_toolbar)
            except KeyboardInterrupt:
                # Ctrl+C at the prompt cancels the current line (REPL idiom).
                continue
            except EOFError:
                # Ctrl+D exits.
                break

            line = line.strip()
            if not line:
                continue
            action = _dispatch_slash(line)
            if action == "quit":
                break
            if action == "clear":
                print("\x1b[2J\x1b[H", end="")
                continue
            if action == "help":
                _print_help()
                continue
            if action == "unknown":
                print(f"unknown command: {line.split()[0]} (try /help)", file=sys.stderr)
                continue
            _run_turn(agent, line, args)
    finally:
        store.close()
    print("bye")
    return 0
