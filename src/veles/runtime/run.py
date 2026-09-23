"""Running an agent: the history compressor, the token budget and the run itself.

`run_agent_streaming_aware` runs one prompt (streamed to stdout with
`--stream`) inside `budget_scope`, which also carries the cumulative budget
across claude/gemini CLI delegate hops via `<project>/.veles/budget.state.json`.
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import sys
from pathlib import Path

from veles.core.agent import Agent
from veles.core.budget_state import BudgetSnapshot, save_atomic
from veles.core.budget_state import load as load_budget_snapshot
from veles.core.context import TokenBudget, reset_budget, set_budget
from veles.core.context_compressor import CompressionConfig, make_default_compressor
from veles.core.defaults import DEFAULT_COMPRESS_THRESHOLD_TOKENS
from veles.core.project import Project
from veles.core.provider import Provider
from veles.core.provider_factory import has_api_key, make_provider
from veles.core.routing import route

_compressor_logger = logging.getLogger("veles.core.context_compressor")


def build_compressor(
    project: Project,
    provider: Provider,
    *,
    no_compress: bool = False,
    compressor_model: str | None = None,
    compress_threshold_tokens: int = DEFAULT_COMPRESS_THRESHOLD_TOKENS,
    max_summariser_input_tokens: int | None = None,
    hard_ceiling_tokens: int | None = None,
):
    """Return a history compressor for a run, or None when disabled.

    The summariser provider and model come from `route("compressor", project)`;
    `compressor_model` overrides the model. `provider` (the run's own) is not
    used — the summariser is routed on its own. A disabled compressor logs a
    WARNING: long sessions without one hit the model's context limit, and a
    silent fallback once hid that root cause.
    """
    del provider
    if no_compress:
        _compressor_logger.warning(
            "compressor disabled: --no-compress passed; long sessions "
            "will eventually hit the model context limit",
        )
        return None
    from veles.core.model_resolver import ConfigurationError

    try:
        routed_provider, routed_model = route("compressor", project)
    except ConfigurationError as exc:
        _compressor_logger.warning("compressor disabled: %s", exc)
        return None
    if not has_api_key(routed_provider):
        _compressor_logger.warning(
            "compressor disabled: no API key for routed provider %r; "
            "long sessions will eventually hit the model context limit",
            routed_provider,
        )
        return None
    model = compressor_model or routed_model
    cfg_kwargs: dict[str, int] = {"threshold_tokens": compress_threshold_tokens}
    if max_summariser_input_tokens is not None:
        cfg_kwargs["max_summariser_input_tokens"] = max_summariser_input_tokens
    if hard_ceiling_tokens is not None:
        cfg_kwargs["hard_ceiling_tokens"] = hard_ceiling_tokens
    return make_default_compressor(
        provider=make_provider(routed_provider, model=model),
        model=model,
        cfg=CompressionConfig(**cfg_kwargs),
        project=project,
    )


def compressor_from_args(args: argparse.Namespace, project: Project, provider: Provider):
    """`build_compressor` with the compressor flags read off `args`."""
    return build_compressor(
        project,
        provider,
        no_compress=bool(getattr(args, "no_compress", False)),
        compressor_model=getattr(args, "compressor_model", None),
        compress_threshold_tokens=int(
            getattr(args, "compress_threshold_tokens", DEFAULT_COMPRESS_THRESHOLD_TOKENS)
        ),
    )


def run_agent_streaming_aware(
    agent: Agent,
    prompt: str,
    args: argparse.Namespace,
    project: Project | None = None,
    *,
    emit_output: bool = True,
):
    """Run the agent, streaming chunks to stdout when `args.stream` is set.

    Returns (result, budget). `emit_output=False` runs silently — no streaming,
    no final print; the caller owns output (`--verify` uses it so the base
    answer isn't shown before verification can supersede it).
    """
    from veles.core.trust import begin_trust_turn, end_trust_turn

    trust_turn_token = begin_trust_turn()
    try:
        if getattr(args, "stream", False) and emit_output:

            def _emit(chunk: str) -> None:
                sys.stdout.write(chunk)
                sys.stdout.flush()

            with budget_scope(args, project=project) as budget:
                result = agent.run(prompt, on_text_delta=_emit)
            sys.stdout.write("\n")
            sys.stdout.flush()
        else:
            with budget_scope(args, project=project) as budget:
                result = agent.run(prompt)
            if emit_output:
                print(result.text)
    finally:
        end_trust_turn(trust_turn_token)
    return result, budget


@contextlib.contextmanager
def budget_scope(args: argparse.Namespace, project: Project | None = None):
    """Install a `TokenBudget` of `args.max_tokens_total` for the duration.

    For a CLI delegate the budget is also written to `budget.state.json`, so the
    Veles MCP server the delegate spawns charges the same budget; what it spent
    is added back on exit."""
    budget = TokenBudget(limit=getattr(args, "max_tokens_total", 0))
    token = set_budget(budget)
    snapshot_path: Path | None = None
    initial_consumed = budget.consumed
    if (
        project is not None
        and getattr(args, "provider", None) in {"claude-cli", "gemini-cli"}
        and budget.limit > 0
    ):
        snapshot_path = project.state_dir / "budget.state.json"
        save_atomic(
            snapshot_path,
            BudgetSnapshot(limit=budget.limit, consumed=initial_consumed),
        )
    try:
        yield budget
    finally:
        if snapshot_path is not None:
            snap = load_budget_snapshot(snapshot_path)
            if snap is not None:
                budget.consumed += max(0, snap.consumed - initial_consumed)
            snapshot_path.unlink(missing_ok=True)
        reset_budget(token)


def print_run_summary(args, result, budget) -> None:
    if not args.verbose:
        return
    parts = [
        f"<finished after {result.iterations} turns",
        f"reason={result.stopped_reason}",
    ]
    if budget.limit > 0:
        parts.append(f"budget={budget.consumed}/{budget.limit}")
    print(", ".join(parts) + ">", file=sys.stderr)
