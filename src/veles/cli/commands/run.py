"""`veles run` — single-prompt agent loop with memory + curator triggers."""

from __future__ import annotations

import argparse
import io
import logging
import os
import sys

from veles.cli._agent_builder import make_worker_factory
from veles.core.memory import SessionStore
from veles.core.project import Project
from veles.core.provider import ProviderError

# M228: one exit code per `stopped_reason`, so a parent process can pick a retry
# policy from `returncode` alone instead of regexing the `--verbose` stderr line.
# Everything stays below 125 (126/127/128+n are shell-reserved).
#
#   0 completed            done
#   1 ProviderError, or an unrecognised non-completion   retry
#   2 config / API key / session not found (see below)   do not retry, fix setup
#   3 max_iterations       re-scope the task
#   4 budget_exhausted     raise --max-tokens-total
#   5 empty                the model produced no final text
#   6 cancelled            interrupted
#   7 truncated            the answer hit the token cap (M254) — raise the cap,
#                          do not retry as-is: the same budget truncates again
#
# `.get(..., 1)` is deliberate: a `stopped_reason` added later degrades to
# "generic failure" and can never be mistaken for success.
EXIT_BY_REASON = {
    "completed": 0,
    "max_iterations": 3,
    "budget_exhausted": 4,
    "empty": 5,
    "cancelled": 6,
    "truncated": 7,
}


def _verify_enabled(args: argparse.Namespace) -> bool:
    """M170 opt-in: `--verify` flag or `VELES_VERIFY_MODE=1`. Default off."""
    return bool(getattr(args, "verify", False)) or os.environ.get("VELES_VERIFY_MODE") == "1"


def _build_escalator(args, project, adv_provider, adv_model, store):
    """Return `escalator(prompt) -> RunResult` that re-runs the prompt on the
    advisor-tier model with the full run tool surface. None when the advisor
    agent can't be built (e.g. missing API key)."""
    from veles.cli._agent_builder import build_command_agent
    from veles.core.providers import is_cli_provider
    from veles.runtime.prompt import system_prompt_from_args
    from veles.runtime.registry import RUN_TOOLS
    from veles.runtime.run import run_agent_streaming_aware

    esc_args = argparse.Namespace(**vars(args))
    esc_args.provider = adv_provider
    esc_args.model = adv_model
    esc_args.stream = False
    tool_aware = is_cli_provider(adv_provider)

    def escalator(prompt: str):
        esc_agent = build_command_agent(
            esc_args,
            project,
            tools=RUN_TOOLS,
            system_prompt=system_prompt_from_args(esc_args, project),
            check_api_key=True,
            tool_aware=tool_aware,
            with_compressor=True,
            store=store,
            session_id=None,
        )
        if esc_agent is None:
            return None
        esc_result, _ = run_agent_streaming_aware(
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
    from veles.core.provider_factory import make_provider
    from veles.runtime.prompt import system_prompt_from_args
    from veles.runtime.registry import RUN_TOOLS, load_skills
    from veles.runtime.run import compressor_from_args

    provider = make_provider(args.provider)
    base_system = system_prompt_from_args(args, project)
    compressor = compressor_from_args(args, project, provider)
    registry = load_skills(project, RUN_TOOLS, provider=provider, model=args.model)
    factory = make_worker_factory(
        args, provider=provider, registry=registry, base_system=base_system, compressor=compressor
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
    if getattr(args, "output", "text") == "json":
        return _run_as_json(args, project)
    return _cmd_run(args, project)


# ---- `--output json` (M326) ----
#
# One object on stdout instead of the answer, so an embedder stops assembling a
# run's outcome from three places: the exit code, a `--verbose` debug line on
# stderr (reason, turns, budget) and `events.jsonl`. stderr is unchanged; tool
# calls stay in `events.jsonl`, already a contract. The keys are locked by
# `tests/test_cli_run_contract.py`.


class _StderrTee:
    """sys.stderr as is, also keeping the `warning:`/`error:` lines Veles prints."""

    def __init__(self, stream, warnings: list[str], errors: list[str]) -> None:
        self._stream, self._warnings, self._errors, self._line = stream, warnings, errors, ""

    def write(self, text: str) -> int:
        self._line += text
        *done, self._line = self._line.split("\n")
        for line in done:
            if line.startswith("warning: "):
                self._warnings.append(line.removeprefix("warning: "))
            elif line.startswith("error: "):
                self._errors.append(line.removeprefix("error: "))
        return self._stream.write(text)

    def flush(self) -> None:
        self._stream.flush()

    def __getattr__(self, name: str):
        return getattr(self._stream, name)


def _warning_log(warnings: list[str], log: logging.Logger) -> logging.Handler:
    """A handler keeping WARNING+ records from `veles.*` (e.g. "compressor
    disabled: …"). While it is attached, logging's last-resort stderr print no
    longer fires, so it prints them as that would — and nowhere when the
    process configured logging itself: stderr stays as it was."""
    handler = logging.StreamHandler(sys.stderr if not log.hasHandlers() else io.StringIO())
    handler.setLevel(logging.WARNING)
    handler.addFilter(lambda record: warnings.append(record.getMessage()) or True)
    return handler


def _run_as_json(args: argparse.Namespace, project: Project) -> int:
    import contextlib
    import json
    import time

    started = time.monotonic()
    warnings: list[str] = []
    errors: list[str] = []
    report: dict = {}
    if getattr(args, "stream", False) or getattr(args, "manager", False):
        errors.append("--output json can't be combined with --stream or --manager")
        rc = 2
    else:
        log = logging.getLogger("veles")
        handler = _warning_log(warnings, log)
        log.addHandler(handler)
        try:
            with contextlib.redirect_stderr(_StderrTee(sys.stderr, warnings, errors)):
                rc = _cmd_run(args, project, report)
        finally:
            log.removeHandler(handler)
    result, budget = report.get("result"), report.get("budget")
    usage = getattr(result, "usage", None)
    payload = {
        "status": result.stopped_reason if result is not None else "error",
        "exit_code": rc,
        "session_id": getattr(result, "session_id", None),
        "answer": getattr(result, "text", None),
        "turns": getattr(result, "iterations", 0),
        "elapsed_s": round(time.monotonic() - started, 3),
        # The main loop's own spend; side calls are in `budget.consumed`.
        "tokens": {
            "prompt": getattr(usage, "prompt_tokens", 0),
            "completion": getattr(usage, "completion_tokens", 0),
            "reasoning": getattr(usage, "reasoning_tokens", 0),
            "total": getattr(usage, "total_tokens", 0),
        },
        "budget": {
            "consumed": getattr(budget, "consumed", 0),
            "limit": getattr(budget, "limit", 0),
        },
        "warnings": warnings,
        "error": errors[0] if errors else None,
    }
    print(json.dumps(payload, ensure_ascii=False))
    return rc


def _cmd_run(args: argparse.Namespace, project: Project, report: dict | None = None) -> int:
    """The run itself. With `report` (`--output json`) the answer is not printed;
    the result and the budget are left in `report` for the JSON line instead."""
    # Lazy imports so monkey-patches on the owning modules win at call time.
    from veles.cli._agent_builder import build_command_agent
    from veles.cli._console import check_provider, ensure_api_key
    from veles.cli._project import _touch_active_project
    from veles.core.model_resolver import (
        ConfigurationError,
        ensure_model_configured,
        provider_source,
        resolve_effective_model,
    )
    from veles.runtime.learning import (
        maybe_refresh_nl_routing,
        maybe_refresh_self_doc,
        maybe_run_idle_curator,
        maybe_run_insight_extractor,
        maybe_run_post_turn_curator,
        maybe_run_subproject_proposer,
        maybe_suggest_promotions,
    )
    from veles.runtime.prompt import apply_project_slash_prefix, system_prompt_from_args
    from veles.runtime.registry import RUN_TOOLS
    from veles.runtime.run import print_run_summary, run_agent_streaming_aware

    # M165: resolve provider + model from config (explicit flag → project
    # `[engine]` → user defaults) instead of letting the bare argparse
    # default through. An unconfigured model errors clearly rather than
    # silently booting on a cloud model.
    args.provider, named = provider_source(args, project)
    # The provider first: a typo there is the error to show, not the missing model.
    if not check_provider(args.provider, reason=named):
        return 2
    try:
        args.model = ensure_model_configured(resolve_effective_model(args, project))
    except ConfigurationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not ensure_api_key(args.provider):
        return 2

    project, args.prompt = apply_project_slash_prefix(project, args.prompt)
    _touch_active_project(project)

    # M122f: explicit-opt-in manager-spawn dispatch — `--manager` flag or
    # `VELES_MANAGER_MODE=1`, default off. On success returns the writer's
    # final text and skips the legacy agent path entirely; failures fall
    # through to direct.
    if _maybe_run_via_manager(args, project):
        return 0

    maybe_run_idle_curator(args, project)

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
            system_prompt = system_prompt_from_args(args, project)

        # M152: shared construction spine. `check_api_key=False` — the key
        # was already gated at the top of cmd_run (before the manager path
        # and idle curator), so the factory must not re-check it here.
        agent = build_command_agent(
            args,
            project,
            tools=RUN_TOOLS,
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
            result, budget = run_agent_streaming_aware(
                agent, args.prompt, args, emit_output=not verify_on and report is None
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
            if report is None:
                print(result.text)
        print(f"<session={result.session_id}>", file=sys.stderr)
        print_run_summary(args, result, budget)
        rc = EXIT_BY_REASON.get(result.stopped_reason, 1)
        if report is not None:
            report.update(result=result, budget=budget)
    finally:
        store.close()
    maybe_run_insight_extractor(args, project, result.history, result.session_id)
    maybe_run_post_turn_curator(args, project)
    maybe_run_subproject_proposer(args, project)
    maybe_suggest_promotions(args, project)
    maybe_refresh_nl_routing(args, project)
    maybe_refresh_self_doc(project)
    return rc
