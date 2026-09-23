"""The daemon's background runners: jobs, reminders and dreams.

`attach_background_runners` builds them onto `DaemonState` so the aiohttp
lifecycle in `server.py` starts and stops them.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def attach_background_runners(
    state, project, agent_factory, provider_name: str, *, args=None, store=None
):
    """Wire the JobRunner, ReminderRunner and DreamRunner onto `state`. Returns
    the `JobsStore` so the caller can close it in `finally`.

    `args`/`store`: when supplied, additionally wire the structured
    background-op machinery — the ingest and research kind handlers, the
    notify+resume completion callback, and the daemon-wide sub-agent factory
    (`state.subagent_factory`, capped at [run]) that makes delegate/wiki_add
    usable in daemon turns at all."""
    from veles.channels.delivery import DeliveryRouter
    from veles.core.dream_runner import DreamRunner
    from veles.core.job_runner import JobRunner
    from veles.core.jobs_store import JobsStore
    from veles.core.memory import SessionStore
    from veles.core.routing.ensemble import route

    # The dream's LLM steps (insight extraction + consolidation) resolve their
    # provider AND model together through routing, like the post-turn insight
    # extractor. Reusing the daemon's main provider with dreaming's hard-coded
    # default model asked a local backend for an OpenRouter slug (HTTP 404).
    del provider_name
    from veles.core.model_resolver import ConfigurationError

    try:
        dream_provider_name, dream_model = route("insights", project)
    except ConfigurationError:
        # Unconfigured: the dream runner gets an empty spec and skips at
        # dream-time (lazy `_provider_for_dream`); daemon start is unaffected.
        dream_provider_name, dream_model = "", ""

    # Built now but empty: platform deliverers register once channels start
    # (`channels.start_channel_runners`). A job that fires before its channel
    # is up hits "no deliverer wired" (logged, best-effort). `local`-target
    # output is already persisted under `.veles/jobs/`; the sink only logs it.
    delivery_router = DeliveryRouter(
        local_sink=lambda text: logger.info("job delivery [local]: %.200s", text or ""),
    )
    state.delivery_router = delivery_router

    from veles.core.job_schedule import resolve_schedule_tz

    kind_handlers = None
    on_op_finished = None
    if args is not None and store is not None:
        from veles.daemon.agent_factory import make_scoped_subagent_factory
        from veles.daemon.background_ops import (
            make_ingest_kind_handler,
            make_on_op_finished,
            make_research_kind_handler,
        )

        # Every factory resolves the model the same way the chat does — a named
        # daemon's `[daemon.<name>] model` applies to its workers too.
        session = state.session_name
        kind_handlers = {
            "ingest": make_ingest_kind_handler(
                args, project=project, store=store, daemon_session=session
            ),
            "research": make_research_kind_handler(
                args, project=project, store=store, daemon_session=session
            ),
        }
        on_op_finished = make_on_op_finished(state)
        state.subagent_factory = make_scoped_subagent_factory(
            args, project=project, store=store, toolset="run", daemon_session=session
        )

    from veles.daemon.background_ops import make_proactive_binder

    jobs_store = JobsStore(project.memory_db_path)
    state.job_runner = JobRunner(
        store=jobs_store,
        agent_factory=agent_factory,
        output_root=project.jobs_dir,
        delivery_router=delivery_router,
        # Calendar schedules fire in the project's `[schedule] timezone`,
        # host-local by default.
        tz=resolve_schedule_tz(project),
        kind_handlers=kind_handlers,
        on_op_finished=on_op_finished,
        # What a job sends into a chat is recorded in that chat's session,
        # the same way reminders are.
        on_delivered=make_proactive_binder(state),
    )

    # The reminder sweep shares the SAME delivery_router (the one channels
    # register on — a fresh router would never reach Telegram). Dream-source
    # notices resolve their target (the last active channel) at delivery time,
    # and every attempt is audited to `proactive_deliveries`.
    from veles.core.proactive.delivery_log import DeliveryLog
    from veles.core.proactive.target_resolver import resolve_last_active_target
    from veles.core.reminder_runner import ReminderRunner
    from veles.core.tasks_store import TasksStore

    state.reminder_runner = ReminderRunner(
        store=TasksStore(project.memory_db_path),
        delivery_router=delivery_router,
        target_resolver=lambda: resolve_last_active_target(state),
        delivery_log=DeliveryLog(project.memory_db_path),
        on_delivered=make_proactive_binder(state),
    )

    def _provider_for_dream():
        from veles.core.provider_factory import make_provider

        return make_provider(dream_provider_name)

    def _history_loader():
        from veles.core.curator_state import load as _load_curator

        s = _load_curator(project.state_dir / "curator.state.json")
        sub = SessionStore(project.memory_db_path)
        try:
            for sess in sub.list_sessions_since(s.last_curated_at, limit=20):
                yield sess.id, sub.load_messages(sess.id)
        finally:
            sub.close()

    def _proactive_history_loader():
        # Corpus for proactive event extraction: the most recent sessions by
        # activity, oldest→newest so the char-cap keeps the freshest tail.
        # Independent of the curation cursor — a session curated seconds ago
        # must still be visible to proactivity.
        sub = SessionStore(project.memory_db_path)
        try:
            recent = sub.list_sessions(limit=20)  # newest-first
            for sess in reversed(recent):
                yield sess.id, sub.load_messages(sess.id)
        finally:
            sub.close()

    def _runtime_session_loader():
        # All launched runtime sessions (incl. soft-deleted), so the dream's
        # consolidation is aware of the whole fleet.
        from veles.core.runtime_sessions import (
            RuntimeSessionStore,
            runtime_session_digest,
        )

        runtime_store = RuntimeSessionStore(project.memory_db_path)
        try:
            return runtime_session_digest(runtime_store.list(include_deleted=True))
        finally:
            runtime_store.close()

    state.dream_runner = DreamRunner(
        project=project,
        state=state,
        provider_factory=_provider_for_dream,
        consolidation_model=dream_model,
        insight_history_loader=_history_loader,
        runtime_session_loader=_runtime_session_loader,
        proactive_history_loader=_proactive_history_loader,
    )
    return jobs_store
