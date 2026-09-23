"""Entry-point default provider/model ids.

Kept in `veles.core` so `core.model_resolver` does not import from
`veles.cli` (M194 — core must not reach up into the CLI layer). Re-exported
by `veles.cli._parsers._common` so the argparse `default=...` wiring and
existing imports keep working unchanged.
"""

from __future__ import annotations

# Empty by design (M165): no hardcoded fallback model. The effective model is
# resolved from explicit `--model`, the project `[engine] model`, or the user
# `default_model`; when none is configured veles raises a clear "model not
# configured" error instead of silently using a cloud model.
DEFAULT_MODEL = ""
DEFAULT_PROVIDER = "openrouter"

# Where a daemon binds when neither a flag nor `[daemon]` config says otherwise.
DEFAULT_DAEMON_HOST = "127.0.0.1"
DEFAULT_DAEMON_PORT = 8765
