"""Building the agents daemon turns run.

The immutable `FactorySettings` snapshot, the per-turn `build_agent_for_turn`
assembler, the `AgentFactory` closures (`make_agent_factory`,
`make_worker_agent_factory`, `make_scoped_subagent_factory`), the post-turn
learning-loop hook (`make_post_turn_hook`) and the verify hook
(`make_verify_hook`). It never imports `veles.cli`: the prompt,
tools, compressor and learning hooks come from `veles.runtime`, the provider from
`veles.core.provider_factory`. Those are imported lazily inside each function
so tests can patch them on their owning module at call time.
"""

from __future__ import annotations

import argparse
import dataclasses
import logging
import sys

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True, slots=True)
class FactorySettings:
    """Immutable snapshot of the daemon's per-process agent settings.

    `make_agent_factory` reads them once from `args` at startup; the
    factory closure carries this dataclass instead of a bag of locals
    so `build_agent_for_turn` is testable in isolation."""

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


def factory_settings_from_args(
    args: argparse.Namespace, project, *, daemon_session: str | None = None
) -> FactorySettings:
    from veles.core.defaults import DEFAULT_COMPRESS_THRESHOLD_TOKENS, DEFAULT_MAX_ITERATIONS
    from veles.core.model_resolver import (
        ensure_model_configured,
        resolve_effective_model,
        resolve_effective_provider,
    )
    from veles.core.project_config import get_section, load_project_config

    # M130: resolve the daemon's main provider/model through the unified
    # cascade — explicit `--provider`/`--model`, then project `[engine]`,
    # then user `[user] default_*`, then the argparse DEFAULT — the SAME
    # cascade the TUI uses (`resolve_effective_*`). The old hand-rolled
    # `cli_model or cfg_model or DEFAULT_MODEL` skipped the user layer, so
    # a daemon in a project that has no own `[engine]` booted on
    # `DEFAULT_MODEL` (anthropic/claude-sonnet-4.6) even when the user had
    # picked ollama at user scope — a provider/model mismatch. An absent
    # `--provider`/`--model` defers to the cascade (see `model_resolver`).
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

    return FactorySettings(
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
        # (`route("compressor")`, which inherits `[engine]`). The daemon
        # parser doesn't register `--compressor-model`, so the old getattr
        # fallback to `DEFAULT_COMPRESSOR_MODEL` hard-pinned every daemon's
        # compressor to `anthropic/claude-haiku-4.5`, overriding routing —
        # a fully-local `[engine]=ollama` project still summarised on
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


def _effective_ceilings(settings: FactorySettings) -> tuple[int, int]:
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


def build_agent_for_turn(  # noqa: PLR0913
    settings: FactorySettings,
    *,
    project,
    store,
    session_id: str | None,
    prompt: str | None,
    system_prompt_override: str | None = None,
    provider=None,
    compressor=_UNSET,
    tools: tuple[str, ...] | None = None,
    mode: str | None = None,
    extra_system: str | None = None,
    toolless: bool = False,
):
    """Assemble one Agent for a single turn.

    `mode` / `extra_system` / `toolless` (M280): what an agent mode asks of its
    agent, mirroring the REPL factory (`cli/repl/runtime.py`). `planning` gets
    the read-only planning toolset and `plan_mode`; every mode's
    `system_block` and a phase's `extra_system` are appended to the prompt;
    `toolless` hands the turn an empty registry (GoalMode's interview). The
    REPL's terminal behaviour block is deliberately not carried over.

    The system prompt is rebuilt on every turn (M108) — adapters re-emit
    it on every API call, and the Telegram bot needs the AGENTS.md
    context refreshed for follow-up messages.

    `provider` / `compressor` (M158-followup): both are fixed at daemon
    launch (M127), so `make_agent_factory` builds them ONCE and passes
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
    `make_worker_agent_factory` for manager-spawn sub-agents so
    workers see the project AGENTS.md plus their role-specific
    instructions."""
    from veles.core.agent import Agent
    from veles.core.provider_factory import make_provider
    from veles.core.tools.registry import Registry
    from veles.runtime.prompt import build_run_system_prompt
    from veles.runtime.registry import PLANNING_TOOLS, RUN_TOOLS, load_skills
    from veles.runtime.run import build_compressor

    if provider is None:
        provider = make_provider(settings.provider_name, settings.model)
    is_planning = mode == "planning"
    if toolless:
        registry = Registry()
    else:
        registry = load_skills(
            project,
            # M204: `tools` narrows the surface for scoped sub-agents (e.g. the
            # [ingest] set for background ingest workers — no run_shell/fetch_url,
            # B1). Default stays the full run surface; planning gets its own.
            tools if tools is not None else (PLANNING_TOOLS if is_planning else RUN_TOOLS),
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

        # Log project path + the id we probed so an operator can tell a
        # one-time orphan (a single re-alloc, then continuity) from a
        # fresh-every-turn loop (id changes every message → unstable
        # project/session resolution) when diagnosing lost history.
        _logging.getLogger("veles.daemon").warning(
            "stale session_id %s not in store (project=%s); allocating fresh session",
            session_id,
            project.root,
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
    if mode is not None or extra_system:
        from veles.core.modes import get_mode

        # A toolless turn (GoalMode's interview) carries its own phase prompt;
        # the planning block made it tell the user to "/mode writing" — in a
        # goal, exactly wrong (live-seen in M280b). Same rule as the REPL.
        block = get_mode(mode).system_block.strip() if mode is not None and not toolless else ""
        chunks = [c for c in (system_prompt, block, (extra_system or "").strip()) if c]
        system_prompt = "\n\n".join(chunks) or None
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
        plan_mode=is_planning,
    )


def make_agent_factory(
    args: argparse.Namespace, *, project, store, state=None, daemon_session: str | None = None
):
    """Build an `AgentFactory` for the daemon, mirroring `veles run`.

    Thin wrapper over `build_agent_for_turn` — captures `settings`,
    `project`, `store` in the closure; per-turn args (`session_id`,
    `prompt`) come through the factory signature. JobRunner calls
    `factory(None)` for batch jobs (no prompt → no recall); the HTTP
    and in-process backends pass the user prompt so recall is
    query-aware.

    Model and provider are fixed at daemon launch from config
    (`[engine]` / `[routing.tasks]`), so every turn builds with the same
    config-derived `settings`. The `state`
    param is retained for signature stability (mode overrides, future use).

    M158-followup: because provider + compressor are launch-fixed (M127),
    build them once on the **first turn** and reuse them afterwards (warm HTTP
    connection pool instead of a fresh client per turn). Only the per-turn
    `build_agent_for_turn` work (recall-aware system prompt, skills registry,
    session probe) reruns. Build is *lazy* (first turn, not factory creation)
    so the daemon still boots without an API key / reachable provider — it
    constructs the provider only when it actually serves a turn. The model is
    still threaded per turn via `settings.model`, so reuse never pins the
    model. (The TUI's live `/model` runs through its own factory in
    `tui/__init__.py`, which already shares one provider the same way —
    nothing here touches it.)
    """
    del state  # M127: no model/provider override lookup — config is fixed.
    settings = factory_settings_from_args(args, project, daemon_session=daemon_session)

    factory_logger = logging.getLogger("veles.daemon.agent_factory")

    # First-turn-lazy, then reused. `make_provider` / `build_compressor` are
    # imported at call time so tests can patch them on their owning modules.
    # A concurrent first-turn
    # race would at worst build a second (equivalent) provider that the dict
    # write supersedes — harmless, so no lock.
    reused: dict[str, object] = {}

    def _reused_provider_and_compressor():
        if "provider" not in reused:
            from veles.core.provider_factory import make_provider
            from veles.runtime.run import build_compressor

            provider = make_provider(settings.provider_name)
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

    def factory(
        session_id: str | None,
        *,
        prompt: str | None = None,
        mode: str | None = None,
        extra_system: str | None = None,
        toolless: bool = False,
    ):
        # One INFO line per turn — daemon admins can grep this to confirm
        # which model/provider the config resolved to for each session.
        factory_logger.info(
            "session=%s using model=%s provider=%s mode=%s",
            session_id,
            settings.model,
            settings.provider_name,
            mode or "default",
        )
        provider, compressor = _reused_provider_and_compressor()
        return build_agent_for_turn(
            settings,
            project=project,
            store=store,
            session_id=session_id,
            prompt=prompt,
            provider=provider,
            compressor=compressor,
            mode=mode,
            extra_system=extra_system,
            toolless=toolless,
        )

    return factory


def make_worker_agent_factory(
    args: argparse.Namespace, *, project, store, daemon_session: str | None = None
):
    """M124: build a `(**kwargs) -> Agent` factory for manager-spawn workers.

    The orchestration `spawn(role, prompt, *, agent_factory, ...)`
    contract is `agent_factory(**kwargs)` with `system_prompt` injected
    when a role-specific prompt resolves. The daemon's regular factory
    has a different shape (`(session_id, *, prompt) -> Agent`), so we
    bridge — pulling `system_prompt` out of kwargs and routing through
    `build_agent_for_turn` with the new `system_prompt_override`
    parameter.

    Each spawn call allocates a fresh sub-session (`session_id=None`)
    so explorer/writer histories stay separate — the no-telephone-game
    contract preserves explorer output verbatim in the writer's
    composed prompt (see `core.orchestration.manager.decompose_and_run`).
    """
    settings = factory_settings_from_args(args, project, daemon_session=daemon_session)

    def factory(**kwargs):
        worker_system_prompt = kwargs.get("system_prompt")
        return build_agent_for_turn(
            settings,
            project=project,
            store=store,
            session_id=None,
            prompt=None,
            system_prompt_override=worker_system_prompt,
        )

    return factory


def make_scoped_subagent_factory(
    args: argparse.Namespace,
    *,
    project,
    store,
    toolset: str,
    daemon_session: str | None = None,
):
    """M204: a `factory(*, system_prompt, tools) -> Agent` for sub-agents whose
    registry is CAPPED at the named toolset.

    This is what makes `delegate`/`wiki_add` work under the daemon at all —
    `set_subagent_factory` used to be wired only in the REPL. The cap is the
    security half (B1): a background ingest worker built through
    `toolset="ingest"` can never obtain `run_shell`/`fetch_url`, whatever the
    requested `tools` list says — requests are intersected with the toolset
    ceiling, and an empty intersection falls back to the full (still-capped)
    set. Fresh sub-session per call (`session_id=None`), mirroring
    `make_worker_agent_factory`.
    """
    from veles.core.tools.toolsets import TOOLSETS

    settings = factory_settings_from_args(args, project, daemon_session=daemon_session)
    ceiling: tuple[str, ...] = TOOLSETS[toolset]

    def factory(*, system_prompt: str | None = None, tools: list[str] | None = None, **_kw):
        allowed = set(ceiling)
        resolved = tuple(t for t in (tools or ceiling) if t in allowed) or ceiling
        return build_agent_for_turn(
            settings,
            project=project,
            store=store,
            session_id=None,
            prompt=None,
            system_prompt_override=system_prompt,
            tools=resolved,
        )

    return factory


def make_post_turn_hook(args: argparse.Namespace, project):
    """Closure that runs the same post-turn learning loop as `cmd_run`.

    Synchronous; fires curator/insights/proposer/etc. after every daemon
    run. Each step is best-effort — a failure in one doesn't block the
    others, and never propagates to the run worker. `args` here is the
    `daemon start` Namespace, which is missing some flags the curator
    helpers consult (e.g. `--no-curator`); they read those via
    `getattr` with safe defaults so absence is interpreted as "default
    behaviour" (mirrors `veles run`).

    M184: the daemon/channel start Namespace carries `provider=None` when no
    `--provider` was passed — provider flows from project/user config. The
    continuous-curator eligibility gate keys off `args.provider`, so without
    this resolution it sees None and silently disables the curator (a wiki-llm
    diary bot accumulated 5 sessions but 0 curated wiki pages). Resolve the
    effective provider into `args` here — the same step `cmd_run` performs
    before its own post-turn block — so the daemon and every channel that
    reuses `state.post_turn_hook` curate correctly.
    """
    from veles.core.model_resolver import resolve_effective_provider

    if not getattr(args, "provider", None):
        args.provider = resolve_effective_provider(args, project)

    from veles.runtime.learning import (
        maybe_refresh_nl_routing,
        maybe_refresh_self_doc,
        maybe_run_insight_extractor,
        maybe_run_post_turn_curator,
        maybe_run_subproject_proposer,
        maybe_suggest_promotions,
    )

    def hook(result) -> None:
        for step in (
            lambda: maybe_run_insight_extractor(args, project, result.history, result.session_id),
            lambda: maybe_run_post_turn_curator(args, project),
            lambda: maybe_run_subproject_proposer(args, project),
            lambda: maybe_suggest_promotions(args, project),
            lambda: maybe_refresh_nl_routing(args, project),
            lambda: maybe_refresh_self_doc(project),
        ):
            try:
                step()
            except Exception as exc:
                print(
                    f"post-turn hook failed ({type(exc).__name__}: {exc})",
                    file=sys.stderr,
                )

    return hook


def _verify_enabled(project) -> bool:
    """M170b gate: `VELES_VERIFY_MODE=1` env override, else `[verify] enabled`
    in the project config. Default off. Config is the primary switch (a global
    env that doubles token spend on every channel message is a footgun)."""
    import os

    if os.environ.get("VELES_VERIFY_MODE") == "1":
        return True
    from veles.core.project_config import get_section, load_project_config

    section = get_section(load_project_config(project), "verify")
    return bool(section.get("enabled", False))


def make_verify_hook(
    args: argparse.Namespace, *, project, store, daemon_session: str | None = None
):
    """M170b: build the daemon `verify_hook(prompt, result) -> result`, or
    None when verify is off for this project.

    Mirrors the `veles run` wiring but daemon-side: the routed advisor judges
    the answer against its evidence trace; a confident FAIL re-runs the prompt
    on the advisor-tier model. The re-run uses the **base session_id** so a
    persistent channel chat keeps its history (a fresh session would make the
    bot "forget everything" on the first escalation). Same-model advisor routes
    are skipped (no real escalation). Everything is best-effort — the callers
    (`run_agent_in_background` and, M170c, `run_manager_in_background`) suppress
    exceptions and keep the base answer.
    """
    if not _verify_enabled(project):
        return None
    settings = factory_settings_from_args(args, project, daemon_session=daemon_session)

    def hook(prompt: str, result):
        from veles.core.model_resolver import ConfigurationError
        from veles.core.routing import route
        from veles.core.verify import (
            make_advisor_verifier,
            render_evidence,
            verify_and_maybe_escalate,
        )

        verifier = make_advisor_verifier(render_evidence(result.history))

        def escalator(p: str):
            try:
                adv_provider, adv_model = route("advisor", project)
            except ConfigurationError:
                return None
            if (adv_provider, adv_model) == (settings.provider_name, settings.model):
                return None  # advisor == base model — re-running it is pointless
            adv_settings = dataclasses.replace(
                settings, provider_name=adv_provider, model=adv_model
            )
            try:
                adv_agent = build_agent_for_turn(
                    adv_settings,
                    project=project,
                    store=store,
                    session_id=result.session_id,  # continuity: same chat session
                    prompt=p,
                )
                return adv_agent.run(p)
            except Exception:
                return None

        outcome = verify_and_maybe_escalate(
            prompt, result.text, verifier=verifier, escalator=escalator
        )
        if outcome.escalated and outcome.escalated_result is not None:
            return outcome.escalated_result
        return result

    return hook
