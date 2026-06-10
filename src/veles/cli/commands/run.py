"""`veles run` — single-prompt agent loop with memory + curator triggers."""

from __future__ import annotations

import argparse
import sys

from veles.core.agent import Agent
from veles.core.memory import SessionStore
from veles.core.project import Project
from veles.core.provider import ProviderError


def _maybe_run_via_manager(args: argparse.Namespace, project: Project) -> bool:
    """M122f: explicit-opt-in manager-spawn dispatch.

    Returns True iff the manager path ran the user's prompt to
    completion (and the writer's text was printed). False means
    the caller should continue with the legacy direct-agent path.

    Activation is opt-in, default OFF (the legacy single-agent loop):
    pass `--manager` (force on) or set `VELES_MANAGER_MODE=1`. The
    auto-heuristic is disabled (`use_heuristic_default=False`) so a
    plain `veles run` never silently spends tokens on N sub-agents.
    Manager failures still fall through to the legacy path — never
    break the user's turn over an orchestration hiccup.
    """
    from veles.core.orchestration import (
        decompose_and_run,
        should_use_manager,
    )

    force = True if getattr(args, "manager", False) else None
    if not should_use_manager(args.prompt, force=force, use_heuristic_default=False):
        return False
    # Build an agent factory that closes over the existing
    # provider / model / registry plumbing. Sub-agents see the
    # same tool surface as the direct agent would.
    from veles.cli import (
        _RUN_TOOLS,
        _build_compressor,
        _build_run_system_prompt,
        _load_skills,
        _make_provider,
    )

    provider = _make_provider(args.provider)
    base_system = _build_run_system_prompt(args, project)
    compressor = _build_compressor(args, project, provider)
    registry = _load_skills(project, _RUN_TOOLS, provider=provider, model=args.model)

    def factory(**kwargs):
        # `kwargs.get('system_prompt')` carries the role-specific
        # prompt from `spawn()`. We concatenate it with the base
        # system prompt so workers still see project context.
        worker_system = kwargs.get("system_prompt") or ""
        full_system = (
            f"{base_system}\n\n---\n\n{worker_system}"
            if base_system and worker_system
            else (worker_system or base_system)
        )
        return Agent(
            provider=provider,
            registry=registry,
            model=args.model,
            max_iterations=args.max_iterations,
            system_prompt=full_system,
            verbose=args.verbose,
            compressor=compressor,
        )

    result = decompose_and_run(args.prompt, agent_factory=factory)
    if result.error or not result.final_text:
        sys.stderr.write(
            f"<manager-spawn fell back to direct: {result.error or 'no output'}>\n"
        )
        return False
    # Print writer's text to stdout (matches direct-agent contract).
    sys.stdout.write(result.final_text)
    if not result.final_text.endswith("\n"):
        sys.stdout.write("\n")
    return True


def cmd_run(args: argparse.Namespace, project: Project) -> int:
    # Lazy imports so monkey-patches at `veles.cli._<helper>` win at call time.
    from veles.cli import (
        _PROVIDER_API_KEY_ENVS,
        _RUN_TOOLS,
        _build_run_system_prompt,
        _ensure_api_key,
        _maybe_apply_project_slash_prefix,
        _maybe_refresh_nl_routing,
        _maybe_refresh_self_doc,
        _maybe_run_idle_curator,
        _maybe_run_insight_extractor,
        _maybe_run_post_turn_curator,
        _maybe_run_subproject_proposer,
        _maybe_suggest_promotions,
        _print_run_summary,
        _run_agent_streaming_aware,
        _touch_active_project,
        _warn_if_agents_md_invalid,
        build_command_agent,
    )

    if args.provider in _PROVIDER_API_KEY_ENVS and not _ensure_api_key(args.provider):
        return 2

    project, args.prompt = _maybe_apply_project_slash_prefix(project, args.prompt)
    _touch_active_project(project)
    _warn_if_agents_md_invalid(project)

    # M122f: explicit-opt-in manager-spawn dispatch — `--manager` flag or
    # `VELES_MANAGER_MODE=1`, default off. On success returns the writer's
    # final text and skips the legacy agent path entirely; failures fall
    # through to direct.
    if _maybe_run_via_manager(args, project):
        return 0

    _maybe_run_idle_curator(args, project)

    store = SessionStore(project.memory_db_path)
    try:
        if args.resume is not None:
            existing = store.get_session(args.resume)
            if existing is None:
                print(f"error: session {args.resume} not found", file=sys.stderr)
                return 2
            session_id: str | None = args.resume
            system_prompt: str | None = None
        else:
            session_id = None
            system_prompt = _build_run_system_prompt(args, project)

        # M152: shared construction spine. `check_api_key=False` — the key
        # was already gated at the top of cmd_run (before the manager path
        # and idle curator), so the factory must not re-check it here.
        agent = build_command_agent(
            args,
            project,
            tools=_RUN_TOOLS,
            system_prompt=system_prompt,
            check_api_key=False,
            with_compressor=True,
            store=store,
            session_id=session_id,
            plan_mode=getattr(args, "plan", False),
        )
        try:
            result, budget = _run_agent_streaming_aware(agent, args.prompt, args)
        except ProviderError as exc:
            # M132b: a provider that's unreachable / timed out / returned a
            # 5xx is a clean operational failure, not a veles crash — print
            # the typed, actionable message without a scary traceback. (The
            # TUI/daemon already surface this via the M132 error path.)
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(f"<session={result.session_id}>", file=sys.stderr)
        _print_run_summary(args, result, budget)
        rc = 0 if result.stopped_reason == "completed" else 1
    finally:
        store.close()
    _maybe_run_insight_extractor(args, project, result.history, result.session_id)
    _maybe_run_post_turn_curator(args, project)
    _maybe_run_subproject_proposer(args, project)
    _maybe_suggest_promotions(args, project)
    _maybe_refresh_nl_routing(args, project)
    _maybe_refresh_self_doc(project)
    return rc
