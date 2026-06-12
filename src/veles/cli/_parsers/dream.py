"""Parser for `veles dream`."""

from __future__ import annotations

import argparse

from veles.cli._parsers._common import (
    DEFAULT_PROVIDER,
    PROVIDER_CHOICES,
    add_project_root_flag,
)


def register(sub: argparse._SubParsersAction) -> None:
    dream = sub.add_parser(
        "dream",
        help="Run one background memory-consolidation cycle.",
    )
    add_project_root_flag(dream)
    dream.add_argument(
        "--include-consolidation",
        dest="include_consolidation",
        action="store_true",
        help="Run the expensive LLM consolidation step (needs a provider API key).",
    )
    dream.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Execute all steps but skip the final wiki/state writes.",
    )
    dream.add_argument(
        "--skip-insights", dest="skip_insights", action="store_true",
        help="Skip extracting insights from recent sessions.",
    )
    dream.add_argument(
        "--skip-dedup", dest="skip_dedup", action="store_true",
        help="Skip the skill-deduplication step.",
    )
    dream.add_argument(
        "--skip-promote", dest="skip_promote", action="store_true",
        help="Skip generating skill-promotion suggestions.",
    )
    dream.add_argument(
        "--skip-lint", dest="skip_lint", action="store_true",
        help="Skip linting the wiki for orphan / stale / duplicate pages.",
    )
    dream.add_argument(
        "--provider",
        choices=PROVIDER_CHOICES,
        default=DEFAULT_PROVIDER,
        help=f"Provider for the consolidation sub-agent (default: {DEFAULT_PROVIDER}).",
    )
    dream.add_argument(
        "--consolidation-model",
        dest="consolidation_model",
        default=None,
        help="Override the cheap-model used for consolidation (default: anthropic/claude-haiku-4.5).",
    )
