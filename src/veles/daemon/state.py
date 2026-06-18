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


@dataclass(slots=True)
class SessionOverrides:
    """M126: per-session config that beats `_FactorySettings` defaults.

    A channel (Telegram inline-keyboard, future TUI hotkey, …) can
    POST `PATCH /v1/sessions/{id}` to set any of these; the daemon's
    agent factory reads the override before building the next Agent
    for that session.

    Storage is in-memory only (M126b will persist across restarts);
    `None` means "fall back to daemon default for this field".
    """

    model: str | None = None
    mode: str | None = None
    provider: str | None = None

    def is_empty(self) -> bool:
        return self.model is None and self.mode is None and self.provider is None

    def to_dict(self) -> dict[str, Any]:
        return {"model": self.model, "mode": self.mode, "provider": self.provider}


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
    # M127: retained for struct stability but always None — model is
    # fixed at launch, so `_handle_health` reports the config model and
    # no session ever "overrides" it.
    last_override_session_id: str | None = None
    job_runner: Any | None = None  # M75 JobRunner; lazy import to avoid cycles
    dream_runner: Any | None = None  # M76 DreamRunner
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
    # M126: per-session overrides for model/mode/provider. Keyed by
    # session_id; set via `PATCH /v1/sessions/{id}`.
    session_overrides: dict[str, SessionOverrides] = field(default_factory=dict)

    def get_overrides(self, session_id: str | None) -> SessionOverrides | None:
        if session_id is None:
            return None
        return self.session_overrides.get(session_id)

    def set_overrides(
        self,
        session_id: str,
        *,
        model: str | None = None,
        mode: str | None = None,
        provider: str | None = None,
    ) -> SessionOverrides:
        existing = self.session_overrides.get(session_id, SessionOverrides())
        merged = SessionOverrides(
            model=model if model is not None else existing.model,
            mode=mode if mode is not None else existing.mode,
            provider=provider if provider is not None else existing.provider,
        )
        self.session_overrides[session_id] = merged
        # M127: model/provider are fixed at daemon launch from config and
        # are no longer persisted, rehydrated, or applied. `set_overrides`
        # is now effectively a `mode`-only path (the only field PATCH
        # accepts); nothing is written to the store.
        return merged

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
