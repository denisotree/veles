"""`veles models <provider>` — print the model list a provider exposes.

Thin shell wrapper over `tui.screens._model_fetcher.fetch_models`, so the
same cache + curated-fallback logic the TUI picker uses also powers shell
scripts (`veles models openrouter | grep claude`).
"""

from __future__ import annotations

import argparse
import json
import sys


def cmd_models(args: argparse.Namespace) -> int:
    from veles.tui.screens._model_fetcher import fetch_models

    result = fetch_models(args.provider, refresh=bool(args.refresh))
    if args.as_json:
        json.dump(
            {"provider": args.provider, "source": result.source, "models": result.models},
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
        return 0

    if not result.models:
        print(
            f"no models for provider {args.provider!r} "
            f"(source: {result.source}) — no API key, endpoint unreachable, "
            "or provider has no listing endpoint.",
            file=sys.stderr,
        )
        return 1

    print(f"# provider={args.provider} source={result.source} count={len(result.models)}")
    for model in result.models:
        print(model)
    return 0
