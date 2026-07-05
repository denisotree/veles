"""`veles run` — single-prompt agent loop with memory + curator triggers."""

from __future__ import annotations

import argparse
import os
import sys

from veles.core.agent import Agent
from veles.core.memory import SessionStore
from veles.core.project import Project
from veles.core.provider import ProviderError


def _verify_enabled(args: argparse.Namespace) -> bool:
    """M170 opt-in: `--verify` flag or `VELES_VERIFY_MODE=1`. Default off."""
    return bool(getattr(args, "verify", False)) or os.environ.get("VELES_VERIFY_MODE") == "1"


def _build_escalator(args, project, adv_provider, adv_model, store):
    """Return `escalator(prompt) -> RunResult` that re-runs the prompt on the
    advisor-tier model with the full run tool surface. None when the advisor
    agent can't be built (e.g. missing API key)."""
    from veles.cli import (
        _RUN_TOOLS,
        _build_run_system_prompt,
        _run_agent_streaming_aware,
        build_command_agent,
    )

    esc_args = argparse.Namespace(**vars(args))
    esc_args.provider = adv_provider
    esc_args.model = adv_model
    esc_args.stream = False
    tool_aware = adv_provider in {"claude-cli", "gemini-cli"}

    def escalator(prompt: str):
        esc_agent = build_command_agent(
            esc_args,
            project,
            tools=_RUN_TOOLS,
            system_prompt=_build_run_system_prompt(esc_args, project),
            check_api_key=True,
            tool_aware=tool_aware,
            with_compressor=True,
            store=store,
            session_id=None,
        )
        if esc_agent is None:
            return None
        esc_result, _ = _run_agent_streaming_aware(
            esc_agent, prompt, esc_args, project=project, emit_output=False
        )
        return esc_result

    return escalator


def _maybe_verify_and_escalate(args: argparse.Namespace, project: Project, result, store):
    """M170: opt-in post-run verify→escalate. Returns the (possibly
    escalated) RunResult.

    PASS / UNKNOWN keep the base answer (UNKNOWN = advisor unavailable or
    judge unparseable — never re-run tier-1 on the judge's own malfunction).
    A confident FAIL re-runs the prompt on the routed advisor model and
    returns THAT result, so the printed answer AND the learning-loop hooks
    (insight extractor / curator) operate on the corrected run, not the
    discarded one.
    """
    if not _verify_enabled(args):
        return result
    from veles.core.model_resolver import ConfigurationError
    from veles.core.routing import route
    from veles.core.verify import (
        VerifyVerdict,
        make_advisor_verifier,
        render_evidence,
        verify_and_maybe_escalate,
    )

    verifier = make_advisor_verifier(render_evidence(result.history))

    escalator = None
    adv_provider = adv_model = None
    try:
        adv_provider, adv_model = route("advisor", project)
    except ConfigurationError:
        adv_provider = adv_model = None
    if adv_provider and (adv_provider, adv_model) == (args.provider, args.model):
        print(
            "<verify: advisor route equals the base model; escalation would re-run "
            "the same model — set a stronger [routing.tasks].advisor>",
            file=sys.stderr,
        )
    elif adv_provider:
        escalator = _build_escalator(args, project, adv_provider, adv_model, store)

    outcome = verify_and_maybe_escalate(
        args.prompt, result.text, verifier=verifier, escalator=escalator
    )

    if outcome.verdict is VerifyVerdict.PASS:
        print("<verify: passed>", file=sys.stderr)
    elif outcome.verdict is VerifyVerdict.UNKNOWN:
        print(
            "<verify: inconclusive (advisor unavailable/unparseable) — answer kept>",
            file=sys.stderr,
        )
    else:  # FAIL
        concerns = "; ".join(outcome.concerns) or "unspecified"
        if outcome.escalated and outcome.escalated_result is not None:
            print(
                f"<verify: flagged ({concerns}) — escalated to {adv_provider}:{adv_model}>",
                file=sys.stderr,
            )
            return outcome.escalated_result
        print(
            f"<verify: flagged ({concerns}) — no escalation route; answer kept>",
            file=sys.stderr,
        )
    return result


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
        sys.stderr.write(f"<manager-spawn fell back to direct: {result.error or 'no output'}>\n")
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
    from veles.core.model_resolver import (
        ConfigurationError,
        ensure_model_configured,
        resolve_effective_model,
        resolve_effective_provider,
    )

    # M165: resolve provider + model from config (explicit flag → project
    # `[engine]` → user defaults) instead of letting the bare argparse
    # default through. An unconfigured model errors clearly rather than
    # silently booting on a cloud model.
    args.provider = resolve_effective_provider(args, project)
    try:
        args.model = ensure_model_configured(resolve_effective_model(args, project))
    except ConfigurationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

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
        # M170: under --verify, force buffered output so the base answer
        # isn't shown before verification can supersede it; the final answer
        # (base or escalated) is printed once below.
        verify_on = _verify_enabled(args)
        try:
            result, budget = _run_agent_streaming_aware(
                agent, args.prompt, args, emit_output=not verify_on
            )
        except ProviderError as exc:
            # M132b: a provider that's unreachable / timed out / returned a
            # 5xx is a clean operational failure, not a veles crash — print
            # the typed, actionable message without a scary traceback. (The
            # TUI/daemon already surface this via the M132 error path.)
            print(f"error: {exc}", file=sys.stderr)
            return 1
        if verify_on:
            result = _maybe_verify_and_escalate(args, project, result, store)
            print(result.text)
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
