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

# (question) -> answer | None. None means "no interactive human available"; the
# `ask_user` tool then tells the agent to proceed on its best assumption.
UserQuestionPrompter = Callable[[str], str | None]


def _default_prompter(question: str) -> str | None:
    """Stderr/stdin prompt for the interactive `veles run` path. Returns None
    (skip) when stdin isn't a TTY or autopilot is active — never blocks a
    headless or unattended run on input that won't come."""
    if not sys.stdin.isatty():
        return None
    try:
        from veles.core.autopilot import is_active

        if is_active():
            return None
    except Exception:
        pass
    print(f"\n[agent question] {question}\n> ", file=sys.stderr, end="", flush=True)
    try:
        answer = input().strip()
    except (EOFError, KeyboardInterrupt):
        print("\n(no answer)", file=sys.stderr)
        return None
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


def ask_user_question(question: str) -> str | None:
    """Ask the human `question` via the active prompter. None when no
    interactive human is available."""
    return current_question_prompter()(question)
