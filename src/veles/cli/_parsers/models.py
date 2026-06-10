"""Parser for `veles models <provider> [--refresh] [--json]`."""

from __future__ import annotations

import argparse

from veles.cli._parsers._common import PROVIDER_CHOICES


def register(sub: argparse._SubParsersAction) -> None:
    cmd = sub.add_parser(
        "models",
        help=(
            "List models available for a provider. Cloud providers "
            "(openrouter / openai / gemini) are cached for 24h; local "
            "providers (ollama / llamacpp / openai-compat) are always live."
        ),
    )
    cmd.add_argument("provider", choices=PROVIDER_CHOICES)
    cmd.add_argument(
        "--refresh",
        action="store_true",
        help="Bypass the disk cache (cloud providers only) and re-fetch.",
    )
    cmd.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit the result as a JSON object: {provider, source, models}.",
    )
