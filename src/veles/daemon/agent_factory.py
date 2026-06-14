"""Daemon agent-factory wiring (M153 — moved from `veles.cli.commands.daemon`).

Runtime wiring that builds Agents for daemon turns: the immutable
`_FactorySettings` snapshot, the per-turn `_build_agent_for_turn`
assembler, the `AgentFactory` closures (`_make_agent_factory`,
`_make_worker_agent_factory`), the post-turn learning-loop hook
(`_make_post_turn_hook`) and the JobRunner/DreamRunner wiring
(`_attach_background_runners`). This belongs with `daemon/runner.py` — it is
server runtime, not CLI plumbing — but every helper still resolves its
`veles.cli` dependencies lazily inside the function body, both to avoid
a `daemon → cli` import cycle and to preserve the monkeypatch contract
tests rely on (patching `veles.cli._make_provider` etc. at call time).

All names are re-exported from `veles.cli.commands.daemon` for
backwards compatibility with historic import sites.
"""

from __future__ import annotations

import argparse
import dataclasses
import logging
import sys


def _attach_background_runners(state, project, agent_factory, provider_name: str):
    """Wire the JobRunner + DreamRunner onto `state` so the daemon's
    aiohttp lifecycle picks them up. Returns the `JobsStore` so the
    caller can close it in `finally`."""
    from veles.cli import _make_provider as _make_provider_for_dream
    from veles.core.dream_runner import DreamRunner
    from veles.core.job_runner import JobRunner
    from veles.core.jobs_store import JobsStore
    from veles.core.memory import SessionStore
    from veles.core.routing.ensemble import route

    # The dream's LLM steps (insight extraction + consolidation) resolve
    # their provider AND model together through routing — the same cascade
    # the post-turn insight extractor uses (`route("insights")`). Reusing
    # the daemon's main `provider_name` while letting the model default to
    # dreaming's hardcoded `anthropic/claude-haiku-4.5` decoupled the two:
    # a daemon on a local `[provider]` (e.g. ollama) asked that backend for
    # an OpenRouter slug and got HTTP 404 on every deep-dream cycle. Routing
    # both keeps them consistent (ollama → an ollama model, etc.).
    del provider_name
    dream_provider_name, dream_model = route("insights", project)

    jobs_store = JobsStore(project.memory_db_path)
    state.job_runner = JobRunner(
        store=jobs_store,
        agent_factory=agent_factory,
        output_root=project.jobs_dir,
    )

    def _provider_for_dream():
        return _make_provider_for_dream(dream_provider_name)

    def _history_loader():
        from veles.core.curator_state import load as _load_curator

        s = _load_curator(project.state_dir / "curator.state.json")
        sub = SessionStore(project.memory_db_path)
        try:
            for sess in sub.list_sessions_since(s.last_curated_at, limit=20):
                yield sess.id, sub.load_messages(sess.id)
        finally:
            sub.close()

    def _runtime_session_loader():
        # M135-dream: feed all launched runtime sessions (incl. soft-deleted)
        # into the dream so an active daemon's consolidation is aware of the
        # full fleet (ISSUES 3a).
        from veles.core.runtime_sessions import (
            RuntimeSessionStore,
            runtime_session_digest,
        )

        store = RuntimeSessionStore(project.memory_db_path)
        try:
            return runtime_session_digest(store.list(include_deleted=True))
        finally:
            store.close()

    state.dream_runner = DreamRunner(
        project=project,
        state=state,
        provider_factory=_provider_for_dream,
        consolidation_model=dream_model,
        insight_history_loader=_history_loader,
        runtime_session_loader=_runtime_session_loader,
    )
    return jobs_store


@dataclasses.dataclass(frozen=True, slots=True)
class _FactorySettings:
    """Immutable snapshot of the daemon's per-process agent settings.

    `_make_agent_factory` reads them once from `args` at startup; the
    factory closure carries this dataclass instead of a bag of locals
    so `_build_agent_for_turn` is testable in isolation."""

    provider_name: str
    model: str
    max_iterations: int
    max_tokens: int
    verbose: bool
    no_compress: bool
    compress_threshold: int
    # None → defer to the M125-routed compressor model (`route("compressor")`).
    compressor_model: str | None
    # Sub-agent input cap (sliding-window summariser); None → library default.
    max_summariser_input_tokens: int | None
    # Hard ceiling for Agent's last-line emergency truncate; None → off.
    hard_ceiling_tokens: int | None
    # M158-followup: seconds to memoise discovered skills in the daemon so it
    # stops re-parsing every SKILL.md per turn. 0 disables (re-parse every
    # turn). Bounds how long a runtime-authored skill stays invisible.
    skills_cache_ttl: float = 600.0


def _factory_settings_from_args(
    args: argparse.Namespace, project, *, daemon_session: str | None = None
) -> _FactorySettings:
    from veles.cli import (
        DEFAULT_COMPRESS_THRESHOLD_TOKENS,
        DEFAULT_MAX_ITERATIONS,
    )
    from veles.core.model_resolver import (
        ensure_model_configured,
        resolve_effective_model,
        resolve_effective_provider,
    )
    from veles.core.project_config import get_section, load_project_config

    # M130: resolve the daemon's main provider/model through the unified
    # cascade — explicit `--provider`/`--model`, then project `[provider]`,
    # then user `[user] default_*`, then the argparse DEFAULT — the SAME
    # cascade the TUI uses (`resolve_effective_*`). The old hand-rolled
    # `cli_model or cfg_model or DEFAULT_MODEL` skipped the user layer, so
    # a daemon in a project that has no own `[provider]` booted on
    # `DEFAULT_MODEL` (anthropic/claude-sonnet-4.6) even when the user had
    # picked ollama at user scope — a provider/model mismatch. The daemon
    # parser sets `--provider`/`--model` defaults to None, so an absent
    # flag correctly defers to the cascade rather than counting as
    # explicit.
    provider_name = resolve_effective_provider(args, project, daemon_session=daemon_session)
    # M165: a daemon must not boot on a silent cloud fallback — fail clearly
    # when no model is configured anywhere.
    model = ensure_model_configured(
        resolve_effective_model(args, project, daemon_session=daemon_session)
    )

    _cfg = load_project_config(project)
    compressor_section = get_section(_cfg, "compressor")
    daemon_section = get_section(_cfg, "daemon")

    def _int_or_none(value: object) -> int | None:
        if value is None:
            return None
        try:
            return int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None

    max_summariser_input = _int_or_none(
        getattr(args, "max_summariser_input_tokens", None)
        or compressor_section.get("max_summariser_input_tokens")
    )
    hard_ceiling = _int_or_none(
        getattr(args, "hard_ceiling_tokens", None) or compressor_section.get("hard_ceiling_tokens")
    )

    return _FactorySettings(
        provider_name=provider_name,
        model=model,
        max_iterations=int(getattr(args, "max_iterations", DEFAULT_MAX_ITERATIONS)),
        max_tokens=int(getattr(args, "max_tokens", 4096)),
        verbose=bool(getattr(args, "verbose", False)),
        no_compress=bool(getattr(args, "no_compress", False)),
        compress_threshold=int(
            getattr(args, "compress_threshold_tokens", DEFAULT_COMPRESS_THRESHOLD_TOKENS)
        ),
        # None → let `build_compressor` use the M125-routed compressor model
        # (`route("compressor")`, which inherits `[provider]`). The daemon
        # parser doesn't register `--compressor-model`, so the old getattr
        # fallback to `DEFAULT_COMPRESSOR_MODEL` hard-pinned every daemon's
        # compressor to `anthropic/claude-haiku-4.5`, overriding routing —
        # a fully-local `[provider]=ollama` project still summarised on
        # paid haiku. Defaulting to None defers to the route.
        compressor_model=getattr(args, "compressor_model", None),
        max_summariser_input_tokens=max_summariser_input,
        hard_ceiling_tokens=hard_ceiling,
        # `[daemon] skills_cache_ttl` (seconds); absent → 600s, explicit 0
        # disables (re-parse every turn). `_int_or_none` preserves a literal 0.
        skills_cache_ttl=float(
            ttl
            if (ttl := _int_or_none(daemon_section.get("skills_cache_ttl"))) is not None
            else 600
        ),
    )


# Compressor/Agent ceiling defaults — shared so a compressor cached in the
# factory closure and the per-turn Agent agree on the same numbers.
_DEFAULT_HARD_CEILING = 180_000
_DEFAULT_SUMMARISER_INPUT_CAP = 150_000

# Sentinel for "compressor not supplied — build one". `None` can't be the
# default: `build_compressor` legitimately *returns* None (compression off /
# no API key), and a cached None must be reused, not re-treated as "unset"
# (which would rebuild every turn and defeat the cache).
_UNSET = object()


def _effective_ceilings(settings: _FactorySettings) -> tuple[int, int]:
    """(hard_ceiling, summariser_input) from settings, applying the defaults."""
    hard = (
        settings.hard_ceiling_tokens
        if settings.hard_ceiling_tokens is not None
        else _DEFAULT_HARD_CEILING
    )
    summariser = (
        settings.max_summariser_input_tokens
        if settings.max_summariser_input_tokens is not None
        else _DEFAULT_SUMMARISER_INPUT_CAP
    )
    return hard, summariser


def _build_agent_for_turn(
    settings: _FactorySettings,
    *,
    project,
    store,
    session_id: str | None,
    prompt: str | None,
    system_prompt_override: str | None = None,
    provider=None,
    compressor=_UNSET,
):
    """Assemble one Agent for a single turn.

    The system prompt is rebuilt on every turn (M108) — adapters re-emit
    it on every API call, and the Telegram bot needs the AGENTS.md
    context refreshed for follow-up messages.

    `provider` / `compressor` (M158-followup): both are fixed at daemon
    launch (M127), so `_make_agent_factory` builds them ONCE and passes
    them in for reuse across turns — this keeps the provider's HTTP
    connection pool warm instead of reconstructing the client (+ its TLS
    handshakes) every turn. When omitted (worker-spawn factory, tests)
    they are built here, preserving the original per-call behaviour. The
    **model stays a per-call arg** (`Agent(model=settings.model)`), so
    reuse never pins the model — this mirrors the TUI factory
    (`tui/__init__.py`), which has always shared one provider and switched
    only the per-turn model. The daemon fixes the model anyway (M127); the
    TUI's live `/model` runs through its own separate factory and is
    unaffected by anything here.

    `system_prompt_override` (M124): when set, the worker role's
    system prompt is concatenated with the project context. Used by
    `_make_worker_agent_factory` for manager-spawn sub-agents so
    workers see the project AGENTS.md plus their role-specific
    instructions."""
    from veles.cli import (
        _RUN_TOOLS,
        _load_skills,
        _make_provider,
        build_compressor,
        build_run_system_prompt,
    )
    from veles.core.agent import Agent

    if provider is None:
        provider = _make_provider(settings.provider_name, settings.model)
    registry = _load_skills(
        project,
        _RUN_TOOLS,
        provider=provider,
        model=settings.model,
        skills_cache_ttl=settings.skills_cache_ttl,
    )
    # Channel session maps survive daemon restarts and DB resets, so a
    # caller-supplied session_id may point at a row that no longer
    # exists. Hitting `append_turn` with a dangling id trips the FK
    # constraint and surfaces as `<error: IntegrityError: FOREIGN KEY
    # constraint failed>` to the user. Probe first and re-allocate.
    if session_id is not None and not store.session_exists(session_id):
        import logging as _logging

        _logging.getLogger("veles.daemon").warning(
            "stale session_id %s not in store; allocating fresh session",
            session_id,
        )
        session_id = None
    sid = session_id if session_id is not None else store.create_session()
    # Channel/daemon runs are scoped to one project — proposals about
    # *other* subprojects would leak scope to the user (Mind Palace bug).
    base_system = build_run_system_prompt(project, prompt=prompt or "", include_proposals=False)
    if system_prompt_override:
        system_prompt = (
            f"{base_system}\n\n---\n\n{system_prompt_override}"
            if base_system
            else system_prompt_override
        )
    else:
        system_prompt = base_system
    # Resolve hard-ceiling once so both the compressor (for its sub-
    # agent input cap) and Agent (for emergency truncation) agree.
    effective_hard_ceiling, effective_summariser_input = _effective_ceilings(settings)
    if compressor is _UNSET:
        compressor = build_compressor(
            project,
            provider,
            no_compress=settings.no_compress,
            compressor_model=settings.compressor_model,
            compress_threshold_tokens=settings.compress_threshold,
            max_summariser_input_tokens=effective_summariser_input,
            hard_ceiling_tokens=effective_hard_ceiling,
        )
    return Agent(
        provider=provider,
        registry=registry,
        model=settings.model,
        max_iterations=settings.max_iterations,
        max_tokens=settings.max_tokens,
        store=store,
        session_id=sid,
        verbose=settings.verbose,
        system_prompt=system_prompt,
        compressor=compressor,
        hard_ceiling_tokens=effective_hard_ceiling,
    )


def _make_agent_factory(
    args: argparse.Namespace, *, project, store, state=None, daemon_session: str | None = None
):
    """Build an `AgentFactory` for the daemon, mirroring `veles run`.

    Thin wrapper over `_build_agent_for_turn` — captures `settings`,
    `project`, `store` in the closure; per-turn args (`session_id`,
    `prompt`) come through the factory signature. JobRunner calls
    `factory(None)` for batch jobs (no prompt → no recall); the HTTP
    and in-process backends pass the user prompt so recall is
    query-aware.

    M127: model and provider are fixed at daemon launch from config
    (`[provider]` / `[routing.tasks]`); there is no per-session model or
    provider override anymore (the Telegram `/model` picker was removed).
    Every turn builds with the same config-derived `settings`. The `state`
    param is retained for signature stability (mode overrides, future use).

    M158-followup: because provider + compressor are launch-fixed (M127),
    build them once on the **first turn** and reuse them afterwards (warm HTTP
    connection pool instead of a fresh client per turn). Only the per-turn
    `_build_agent_for_turn` work (recall-aware system prompt, skills registry,
    session probe) reruns. Build is *lazy* (first turn, not factory creation)
    so the daemon still boots without an API key / reachable provider — it
    constructs the provider only when it actually serves a turn. The model is
    still threaded per turn via `settings.model`, so reuse never pins the
    model. (The TUI's live `/model` runs through its own factory in
    `tui/__init__.py`, which already shares one provider the same way —
    nothing here touches it.)
    """
    del state  # M127: no model/provider override lookup — config is fixed.
    settings = _factory_settings_from_args(args, project, daemon_session=daemon_session)

    factory_logger = logging.getLogger("veles.daemon.agent_factory")

    # First-turn-lazy, then reused. `_make_provider` / `build_compressor` are
    # resolved via `veles.cli` at call time to honour the monkeypatch contract
    # (tests patch `veles.cli._make_provider` etc.). A concurrent first-turn
    # race would at worst build a second (equivalent) provider that the dict
    # write supersedes — harmless, so no lock.
    reused: dict[str, object] = {}

    def _reused_provider_and_compressor():
        if "provider" not in reused:
            from veles.cli import _make_provider, build_compressor

            provider = _make_provider(settings.provider_name)
            hard_ceiling, summariser_input = _effective_ceilings(settings)
            reused["provider"] = provider
            reused["compressor"] = build_compressor(
                project,
                provider,
                no_compress=settings.no_compress,
                compressor_model=settings.compressor_model,
                compress_threshold_tokens=settings.compress_threshold,
                max_summariser_input_tokens=summariser_input,
                hard_ceiling_tokens=hard_ceiling,
            )
        return reused["provider"], reused["compressor"]

    def factory(session_id: str | None, *, prompt: str | None = None):
        # One INFO line per turn — daemon admins can grep this to confirm
        # which model/provider the config resolved to for each session.
        factory_logger.info(
            "session=%s using model=%s provider=%s",
            session_id,
            settings.model,
            settings.provider_name,
        )
        provider, compressor = _reused_provider_and_compressor()
        return _build_agent_for_turn(
            settings,
            project=project,
            store=store,
            session_id=session_id,
            prompt=prompt,
            provider=provider,
            compressor=compressor,
        )

    return factory


def _make_worker_agent_factory(args: argparse.Namespace, *, project, store):
    """M124: build a `(**kwargs) -> Agent` factory for manager-spawn workers.

    The orchestration `spawn(role, prompt, *, agent_factory, ...)`
    contract is `agent_factory(**kwargs)` with `system_prompt` injected
    when a role-specific prompt resolves. The daemon's regular factory
    has a different shape (`(session_id, *, prompt) -> Agent`), so we
    bridge — pulling `system_prompt` out of kwargs and routing through
    `_build_agent_for_turn` with the new `system_prompt_override`
    parameter.

    Each spawn call allocates a fresh sub-session (`session_id=None`)
    so explorer/writer histories stay separate — the no-telephone-game
    contract preserves explorer output verbatim in the writer's
    composed prompt (see `core.orchestration.manager.decompose_and_run`).
    """
    settings = _factory_settings_from_args(args, project)

    def factory(**kwargs):
        worker_system_prompt = kwargs.get("system_prompt")
        return _build_agent_for_turn(
            settings,
            project=project,
            store=store,
            session_id=None,
            prompt=None,
            system_prompt_override=worker_system_prompt,
        )

    return factory


def _make_post_turn_hook(args: argparse.Namespace, project):
    """Closure that runs the same post-turn learning loop as `cmd_run`.

    Synchronous; fires curator/insights/proposer/etc. after every daemon
    run. Each step is best-effort — a failure in one doesn't block the
    others, and never propagates to the run worker. `args` here is the
    `daemon start` Namespace, which is missing some flags the curator
    helpers consult (e.g. `--no-curator`); they read those via
    `getattr` with safe defaults so absence is interpreted as "default
    behaviour" (mirrors `veles run`).
    """
    from veles.cli import (
        _maybe_refresh_nl_routing,
        _maybe_refresh_self_doc,
        _maybe_run_insight_extractor,
        _maybe_run_post_turn_curator,
        _maybe_run_subproject_proposer,
        _maybe_suggest_promotions,
    )

    def hook(result) -> None:
        for step in (
            lambda: _maybe_run_insight_extractor(args, project, result.history, result.session_id),
            lambda: _maybe_run_post_turn_curator(args, project),
            lambda: _maybe_run_subproject_proposer(args, project),
            lambda: _maybe_suggest_promotions(args, project),
            lambda: _maybe_refresh_nl_routing(args, project),
            lambda: _maybe_refresh_self_doc(project),
        ):
            try:
                step()
            except Exception as exc:
                print(
                    f"post-turn hook failed ({type(exc).__name__}: {exc})",
                    file=sys.stderr,
                )

    return hook
