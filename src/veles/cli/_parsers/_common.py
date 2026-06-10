"""Shared flag groups and parser defaults reused across verb-parser modules.

`add_common_run_flags` is the canonical agent-loop CLI surface
(`--model/--max-iterations/--provider/--max-tokens-total/--verbose/--stream`
plus the project-root override). Verbs that drive the agent loop
(`run/add/curate/tui/job tick`) call it on their subparser.
"""

from __future__ import annotations

import argparse

DEFAULT_MODEL = "anthropic/claude-sonnet-4.6"
DEFAULT_MAX_ITERATIONS = 30
DEFAULT_MAX_TOKENS_TOTAL = 100_000
DEFAULT_PROVIDER = "openrouter"
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
        help=f"Model id (default: {DEFAULT_MODEL}).",
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
