"""Model-callable delegation — the base decompose → scoped worker → integrate
pattern (VISION §5.3, made model-facing).

A capable *root* agent breaks a task into small subtasks and calls the
`delegate` tool per subtask; each spawns a fresh, context-isolated sub-Agent
with a NARROW toolset, runs it to completion, and returns its report so the root
can accept the result or delegate a correction. This is meant as the default way
to handle non-trivial work, not just migration.

The run loop installs a `SubagentFactory` (it holds the provider/model) via
`set_subagent_factory`, exactly like the mid-turn prompters — the `delegate`
tool has no access to the provider otherwise. A depth counter caps runaway
recursion: a worker granted `delegate` can nest, but only `MAX_DELEGATE_DEPTH`
levels deep.
"""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar, Token
from typing import Any

# Contract: factory(*, system_prompt: str, tools: list[str]) -> Agent-like
# (anything with `.run(prompt) -> RunResult`). Kept structural so this module
# never imports Agent.
SubagentFactory = Callable[..., Any]

MAX_DELEGATE_DEPTH = 3

_factory: ContextVar[SubagentFactory | None] = ContextVar("veles_subagent_factory", default=None)
_depth: ContextVar[int] = ContextVar("veles_delegate_depth", default=0)


def set_subagent_factory(f: SubagentFactory) -> Token:
    return _factory.set(f)


def reset_subagent_factory(token: Token) -> None:
    _factory.reset(token)


def current_subagent_factory() -> SubagentFactory | None:
    return _factory.get()


def current_delegate_depth() -> int:
    return _depth.get()


def enter_delegate() -> Token:
    """Increment the delegation depth for the duration of one nested worker."""
    return _depth.set(_depth.get() + 1)


def exit_delegate(token: Token) -> None:
    _depth.reset(token)
