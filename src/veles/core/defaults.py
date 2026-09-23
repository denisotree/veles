"""Entry-point defaults: provider/model ids, loop budgets, compression, daemon bind.

Kept in `veles.core` so the core, the runtime and the daemon can read them
without importing the CLI. `veles.cli._parsers._common` wires them into the
argparse `default=...` values.
"""

from __future__ import annotations

# Empty by design (M165): no hardcoded fallback model. The effective model is
# resolved from explicit `--model`, the project `[engine] model`, or the user
# `default_model`; when none is configured veles raises a clear "model not
# configured" error instead of silently using a cloud model.
DEFAULT_MODEL = ""
DEFAULT_PROVIDER = "openrouter"

# A high runaway backstop, NOT a task budget. A turn may make as many tool calls
# as the work needs; the real "am I stuck?" stop is the StallGuard (repeats of
# the same tool-call signature → forced answer round) plus the token budget.
DEFAULT_MAX_ITERATIONS = 1000
DEFAULT_MAX_TOKENS_TOTAL = 100_000
DEFAULT_COMPRESSOR_MODEL = "anthropic/claude-haiku-4.5"
DEFAULT_COMPRESS_THRESHOLD_TOKENS = 50_000

# Where a daemon binds when neither a flag nor `[daemon]` config says otherwise.
DEFAULT_DAEMON_HOST = "127.0.0.1"
DEFAULT_DAEMON_PORT = 8765
