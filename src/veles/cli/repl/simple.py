"""The `VELES_REPL_SIMPLE=1` fallback loop for the inline REPL.

A blocking `PromptSession.prompt()` loop kept as a safety net for
terminals where the live inline Application misbehaves. Includes the
prompt-session builder, the inline arrow-key choice picker + free-text
prompter used to answer the agent's `ask_user` questions, and the main
loop. Imports from the lower leaves (`terminal`, `turn`); reaches
`_suspend_live` (which stays in `repl.py`) via a function-local import.
"""

from __future__ import annotations

import sys
import time

from veles.cli.repl.terminal import _CTRL_C_EXIT_WINDOW_S, _settled_status
from veles.cli.repl.turn import (
    _handle_slash,
    _run_mode_turn,
    _run_repl_post_turn_hooks,
    _update_state_after_turn,
)
from veles.core.i18n import t
from veles.core.project import Project


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
    from veles.cli.commands.repl import _suspend_live

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
