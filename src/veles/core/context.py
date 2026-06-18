"""Active-project ContextVar — what wiki tools and other agent-side helpers see.

We use ContextVar (not module global) so pytest can isolate per-test active
projects without leaking across cases, and so future async work doesn't trip
on shared state.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass

from veles.core.project import Project

_active_project: ContextVar[Project | None] = ContextVar("veles_active_project", default=None)


def current_project() -> Project | None:
    return _active_project.get()


def set_active_project(p: Project | None) -> Token:
    return _active_project.set(p)


def reset_active_project(token: Token) -> None:
    _active_project.reset(token)


# ---- origin delivery target (M166) ----
# The channel/chat a turn originated from, as a DeliveryTarget string
# (e.g. "telegram:12345"). Set by the channel run path so tools like
# `task_add` can default `deliver_to` to "reply on this chat" without the
# model having to know the chat id. None outside a channel turn (CLI runs).
_current_origin: ContextVar[str | None] = ContextVar("veles_current_origin", default=None)


def current_origin() -> str | None:
    return _current_origin.get()


def set_origin(origin: str | None) -> Token:
    return _current_origin.set(origin)


def reset_origin(token: Token) -> None:
    _current_origin.reset(token)


# ---- skill call stack (cycle / depth guard for cross-skill composition) ----

_skill_stack: ContextVar[tuple[str, ...]] = ContextVar("veles_skill_stack", default=())


def current_skill_stack() -> tuple[str, ...]:
    return _skill_stack.get()


def push_skill_stack(name: str) -> Token:
    return _skill_stack.set((*_skill_stack.get(), name))


def reset_skill_stack(token: Token) -> None:
    _skill_stack.reset(token)


# ---- cumulative token budget (cost guard for nested sub-agents) ----


@dataclass(slots=True)
class TokenBudget:
    """Cumulative token cap shared across nested agent runs.

    `limit <= 0` means unlimited — no checks happen and `consumed` is still
    tracked for telemetry but never causes refusal.
    """

    limit: int
    consumed: int = 0

    @property
    def remaining(self) -> int:
        if self.limit <= 0:
            return -1  # sentinel for "unlimited"
        return max(0, self.limit - self.consumed)

    @property
    def exhausted(self) -> bool:
        return self.limit > 0 and self.consumed >= self.limit


_token_budget: ContextVar[TokenBudget | None] = ContextVar("veles_token_budget", default=None)


def current_budget() -> TokenBudget | None:
    return _token_budget.get()


def set_budget(b: TokenBudget | None) -> Token:
    return _token_budget.set(b)


def reset_budget(token: Token) -> None:
    _token_budget.reset(token)
