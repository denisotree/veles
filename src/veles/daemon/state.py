"""Daemon-shared in-process state (M51) — held under `app["state"]`.

Wraps the live `Project`, an open `SessionStore`, the token store, the
`AgentFactory` injected at startup, and a dict of `RunHandle`s indexed
by run_id. The state is constructed once per daemon and torn down on
shutdown.

M74 additions: `last_activity_at` (timestamp of the last externally-driven
event — used by the dream idle-timer) plus optional `job_runner` /
`dream_runner` slots populated by M75/M76. Both runner slots are typed
loosely (Any) so this module avoids the import cycle.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from veles.core.memory import SessionStore
from veles.core.project import Project
from veles.daemon.auth import TokenStore
from veles.daemon.runner import AgentFactory, RunHandle

# Agent modes a chat can be switched to (`PATCH /v1/sessions/{id}`, Telegram
# `/mode`). "default" is not one of them: it is the absence of a choice.
CHAT_MODES = frozenset({"auto", "planning", "writing", "goal"})


@dataclass(slots=True)
class ChatModeState:
    """M280: what a session's agent mode carries between turns — the REPL keeps
    the same three fields on `AppState`.

    `mode=None` is the chat's default: the daemon's plain single-agent turn,
    exactly as before M280 (the user chose to keep it rather than route every
    message through AutoMode's classifier). In memory only: after a daemon
    restart a chat is back on its default; a goal stays on disk.
    """

    mode: str | None = None
    last_mode_in_session: str | None = None
    active_goal_id: str | None = None


@dataclass(slots=True)
class DaemonState:
    project: Project
    store: SessionStore
    token_store: TokenStore
    agent_factory: AgentFactory
    # M136: the named daemon session this state belongs to (None = legacy
    # unnamed daemon). Channel startup reads `[daemon.<name>.channels.*]` for
    # a named session, else the global `[channels.*]`.
    session_name: str | None = None
    runs: dict[str, RunHandle] = field(default_factory=dict)
    run_tasks: set[asyncio.Task] = field(default_factory=set)
    started_at: float = 0.0
    last_activity_at: float = field(default_factory=time.time)
    # Provider this daemon was started with (e.g. "openrouter", "ollama").
    # Surfaced via /v1/health so channels can show only the relevant
    # model catalogue — daemon's provider is fixed at startup.
    provider: str | None = None
    # Default model from `_FactorySettings.model` — the fallback used
    # when a session has no override. Surfaced via /v1/health so
    # channels can highlight the effective model in their pickers.
    default_model: str | None = None
    job_runner: Any | None = None  # M75 JobRunner; lazy import to avoid cycles
    dream_runner: Any | None = None  # M76 DreamRunner
    reminder_runner: Any | None = None  # M166 ReminderRunner — pushes due task reminders
    # M165 DeliveryRouter: built at runner-attach time, deliverers registered
    # when channels start, used by the JobRunner to push `deliver_to` output.
    delivery_router: Any | None = None
    channel_runners: list[Any] = field(default_factory=list)
    channel_tasks: list[asyncio.Task] = field(default_factory=list)
    # Platform names of the channels that actually *started* (a declared
    # channel whose token is missing is skipped, so this can be a strict
    # subset of the configured `[channels.*]`). Surfaced via /v1/health
    # and /v1/status so the TUI daemon picker shows what the daemon is
    # really serving instead of re-deriving (and diverging) from config.
    # Kept in lockstep with `channel_runners` — cleared together on stop.
    active_channels: list[str] = field(default_factory=list)
    post_turn_hook: Any | None = None  # Callable[[RunResult], None] — runs curator/insights/etc.
    # M170b: Callable[[str, RunResult], RunResult] — opt-in verify→escalate run
    # before the `completed` event. None = off (the default).
    verify_hook: Any | None = None
    # M124: optional `(**kwargs) -> Agent` factory used by manager-spawn
    # in daemon path. When None, manager-mode is skipped and runs always
    # go through the regular `agent_factory` (legacy single-agent path).
    worker_agent_factory: Any | None = None
    # M280: per-session agent mode, set via `PATCH /v1/sessions/{id}` (Telegram
    # `/mode`) and read by `daemon/turns.py::start_turn`. Replaces M126's
    # `session_overrides`, whose model/provider fields M127 had already
    # forbidden and whose mode nothing ever read.
    chat_modes: dict[str, ChatModeState] = field(default_factory=dict)
    # M204: `factory(*, system_prompt, tools) -> Agent` installed around every
    # daemon turn so delegate/wiki_add can spawn scoped sub-agents (this used
    # to be REPL-only). Built by `_attach_background_runners`, capped at [run].
    subagent_factory: Any | None = None
    # M204: per-session turn serializer — a background-op RESUME turn queues
    # behind a live user turn on the same session instead of racing it.
    session_locks: dict[str, asyncio.Lock] = field(default_factory=dict)

    def session_lock(self, session_id: str) -> asyncio.Lock:
        return self.session_locks.setdefault(session_id, asyncio.Lock())

    def chat_mode(self, session_id: str | None) -> ChatModeState:
        """The session's mode state; a session never switched is on its default."""
        if session_id is None:
            return ChatModeState()
        return self.chat_modes.get(session_id) or ChatModeState()

    def set_chat_mode(self, session_id: str, mode: str | None) -> ChatModeState:
        """Switch a session's mode (`None` = back to the default). Keeps the
        goal and mode-switch history, which a switch must not erase."""
        if mode is not None and mode not in CHAT_MODES:
            raise ValueError(f"unknown mode {mode!r}; expected one of {sorted(CHAT_MODES)}")
        current = self.chat_mode(session_id)
        current.mode = mode
        self.chat_modes[session_id] = current
        return current

    def chat_goal(self, session_id: str | None) -> dict[str, Any] | None:
        """M280b: the goal a chat is running, as `/goal` shows it; None when the
        chat has none or it already ended."""
        from veles.core.goal import read_goal

        goal_id = self.chat_mode(session_id).active_goal_id
        goal = read_goal(self.project.state_dir, goal_id) if goal_id else None
        if goal is None or goal.status != "active":
            return None
        return {
            "id": goal.id,
            "objective": goal.objective,
            "phase": goal.current_phase,
            "steps_done": goal.steps_done,
            "max_steps": goal.budget.max_steps,
            "cost_spent_usd": goal.cost_spent_usd,
            "max_cost_usd": goal.budget.max_cost_usd,
        }

    def cancel_chat_goal(self, session_id: str, reason: str) -> dict[str, Any] | None:
        """Cancel the chat's goal and put the chat back on its default. A drive
        in progress sees the status on its next turn and stops. None when there
        was nothing to cancel."""
        from veles.core.goal import cancel

        goal = self.chat_goal(session_id)
        if goal is None:
            return None
        cancel(self.project.state_dir, goal["id"], reason=reason)
        chat = self.chat_mode(session_id)
        chat.mode = None
        chat.active_goal_id = None
        self.chat_modes[session_id] = chat
        return goal

    def add_run(self, handle: RunHandle) -> None:
        self.runs[handle.run_id] = handle
        self.last_activity_at = time.time()

    def get_run(self, run_id: str) -> RunHandle | None:
        return self.runs.get(run_id)

    def list_runs(self) -> list[RunHandle]:
        return list(self.runs.values())

    def has_running_run(self) -> bool:
        """True if at least one run hasn't finished — used by dream gating."""
        return any(not h.done.is_set() for h in self.runs.values())

    def touch_activity(self) -> None:
        self.last_activity_at = time.time()
