"""Free-text user-question prompter (M148).

Mirrors the M71 approval/trust prompter pattern: a ContextVar-installed
callable that asks the human a free-text clarifying question and returns their
answer. The `ask_user` builtin tool calls through here.

The default prompter serves the interactive `veles run` path (stderr question +
stdin line). It deliberately returns `None` — "no human available" — when
stdin is not a TTY or autopilot is active, so a headless / daemon / unattended
run never blocks on input that will never come. The TUI and channels install
their own prompter for their surface (a TUI bridge installs a non-blocking
skip prompter until M148b wires a real modal).
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from contextvars import ContextVar, Token

# (question, options) -> answer | None. None means "no interactive human
# available"; the `ask_user` tool then tells the agent to proceed on its best
# assumption. `options` (when non-empty) are concrete choices to offer — a
# surface may render them as an interactive picker; the user may still type a
# free-text answer instead of picking one.
UserQuestionPrompter = Callable[[str, list[str] | None], str | None]


def _default_prompter(question: str, options: list[str] | None = None) -> str | None:
    """Stderr/stdin prompt for the interactive `veles run` path. Returns None
    (skip) when stdin isn't a TTY or autopilot is active — never blocks a
    headless or unattended run on input that won't come. Options are listed as a
    numbered menu; the user may type a number or a free-text answer."""
    if not sys.stdin.isatty():
        return None
    try:
        from veles.core.autopilot import is_active

        if is_active():
            return None
    except Exception:
        pass
    print(f"\n[agent question] {question}", file=sys.stderr, flush=True)
    if options:
        for i, opt in enumerate(options, 1):
            print(f"  {i}. {opt}", file=sys.stderr, flush=True)
    print("> ", file=sys.stderr, end="", flush=True)
    try:
        answer = input().strip()
    except (EOFError, KeyboardInterrupt):
        print("\n(no answer)", file=sys.stderr)
        return None
    if options and answer.isdigit() and 1 <= int(answer) <= len(options):
        return options[int(answer) - 1]
    return answer or None


_active: ContextVar[UserQuestionPrompter] = ContextVar(
    "veles_user_question_prompter", default=_default_prompter
)


def current_question_prompter() -> UserQuestionPrompter:
    return _active.get()


def set_question_prompter(p: UserQuestionPrompter) -> Token[UserQuestionPrompter]:
    """Override the prompter for the current ContextVar scope. Returns a token
    the caller resets at end of scope (TUI bridge, channels, tests)."""
    return _active.set(p)


def reset_question_prompter(token: Token[UserQuestionPrompter]) -> None:
    _active.reset(token)


def ask_user_question(question: str, options: list[str] | None = None) -> str | None:
    """Ask the human `question` via the active prompter, optionally offering
    `options` as concrete choices. None when no interactive human is available."""
    return current_question_prompter()(question, options)
