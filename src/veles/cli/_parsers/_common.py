"""Shared flag groups and parser defaults reused across verb-parser modules.

`add_common_run_flags` is the canonical agent-loop CLI surface
(`--model/--max-iterations/--provider/--max-tokens-total/--verbose/--stream`
plus the project-root override). Verbs that drive the agent loop
(`run/add/curate/tui/job tick`) call it on their subparser.
"""

from __future__ import annotations

import argparse

# DEFAULT_MODEL/DEFAULT_PROVIDER live in veles.core.defaults so core.model_resolver
# can import them without reaching up into veles.cli (M194); re-exported here so the
# argparse wiring below and existing `from ..._common import DEFAULT_*` sites keep working.
from veles.core.defaults import DEFAULT_MODEL, DEFAULT_PROVIDER

# A high runaway backstop, NOT a task budget. A turn may make as many tool calls
# as the work needs; the real "am I stuck?" stop is the StallGuard (M144, repeats
# of the same tool-call signature → forced answer round) plus the token budget.
# 30 used to cut off legitimate long jobs (a big migration) mid-task.
DEFAULT_MAX_ITERATIONS = 1000
DEFAULT_MAX_TOKENS_TOTAL = 100_000
DEFAULT_COMPRESSOR_MODEL = "anthropic/claude-haiku-4.5"
DEFAULT_COMPRESS_THRESHOLD_TOKENS = 50_000
PROVIDER_CHOICES = (
    "openrouter",
    "anthropic",
    "openai",
    "gemini",
    "claude-cli",
    "gemini-cli",
    "ollama",
    "llamacpp",
    "openai-compat",
)


class _ExplicitProviderAction(argparse.Action):
    """Record that `--provider` was passed on the command line.

    `resolve_effective_provider` keys off `_provider_explicit` (set here) rather
    than comparing the value to `DEFAULT_PROVIDER`, so `--provider openrouter`
    (which equals the default) is still honored over a differing config default.
    Keeping the stored value a plain string (default `DEFAULT_PROVIDER`) means no
    call site ever sees `None` — zero blast radius (2026-07-07)."""

    def __call__(self, parser, namespace, values, option_string=None):  # type: ignore[override]
        setattr(namespace, self.dest, values)
        namespace._provider_explicit = True


def add_project_root_flag(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--project-root",
        default=None,
        metavar="PATH",
        help="Override project discovery (use this dir as the project root).",
    )


def add_common_run_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Model id (default: resolved from project [engine] model or user "
        "default_model; required if neither is configured).",
    )
    p.add_argument(
        "--max-iterations",
        type=int,
        default=DEFAULT_MAX_ITERATIONS,
        help=f"Max tool-calling iterations (default: {DEFAULT_MAX_ITERATIONS}).",
    )
    p.add_argument(
        "--provider",
        choices=PROVIDER_CHOICES,
        default=DEFAULT_PROVIDER,
        action=_ExplicitProviderAction,
        help=f"LLM provider (default: {DEFAULT_PROVIDER}).",
    )
    p.add_argument(
        "--max-tokens-total",
        type=int,
        default=DEFAULT_MAX_TOKENS_TOTAL,
        metavar="N",
        help=(
            f"Cumulative token budget across all nested calls in this run "
            f"(default: {DEFAULT_MAX_TOKENS_TOTAL}; pass 0 to disable)."
        ),
    )
    p.add_argument("--verbose", "-v", action="store_true", help="Per-turn progress to stderr.")
    p.add_argument(
        "--stream",
        action="store_true",
        help="Stream the response token-by-token to stdout.",
    )
    add_project_root_flag(p)
