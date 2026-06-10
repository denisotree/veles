"""M122d: production-path integration for the manager orchestrator.

The `decompose_and_run` function from M122c is the runtime
foundation; this module is the seam for *opting* into it from the
production agent path. Default behaviour stays single-agent — flipping
the whole installed base to manager-spawn without a feature flag risks
breaking the agent loops that real users depend on.

Three opt-in mechanisms, checked in order:

1. **`VELES_MANAGER_MODE` env var** — `"1"` / `"true"` / `"on"`
   enables manager-spawn for every agent call. `"0"` / `"false"` /
   `"off"` disables. Unset → fall back to heuristic.
2. **Per-call override** — `should_use_manager(prompt, force=True)`
   forces manager-spawn regardless of env / heuristic. Useful for
   callers that have already decomposed elsewhere and want to skip
   the heuristic.
3. **Heuristic** — `needs_decomposition(prompt)` from M122c
   (length + research-keyword classifier).

`run_with_manager_if_eligible(prompt, agent_factory)` is the public
seam call sites use. It returns either the direct agent's reply
text (single-agent path) or `ManagerRunResult.final_text` (manager
path), with `error` surfaced in both cases.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from veles.core.orchestration.manager import (
    ManagerRunResult,
    decompose_and_run,
    needs_decomposition,
)
from veles.core.orchestration.workers import AgentFactory

logger = logging.getLogger(__name__)


MANAGER_ENV = "VELES_MANAGER_MODE"


def env_manager_mode() -> bool | None:
    """Read the env var. Returns:
    - True  — explicitly enabled
    - False — explicitly disabled
    - None  — unset / unrecognised value → defer to heuristic
    """
    raw = os.environ.get(MANAGER_ENV)
    if raw is None:
        return None
    norm = raw.strip().lower()
    if norm in {"1", "true", "on", "yes"}:
        return True
    if norm in {"0", "false", "off", "no"}:
        return False
    return None


def should_use_manager(
    prompt: str,
    *,
    force: bool | None = None,
    use_heuristic_default: bool = True,
) -> bool:
    """Resolve the three opt-in signals into a single decision.

    Priority:
    1. `force` — when not None, short-circuits everything else
       (per-call escape hatch for places that already know).
    2. **Env var** `VELES_MANAGER_MODE` — explicit on/off.
    3. **Heuristic** `needs_decomposition(prompt)` — only consulted
       when `use_heuristic_default=True`.

    Production call sites (`veles run`) pass `use_heuristic_default=
    False` so the manager path activates only on explicit opt-in via
    env var — preserves the legacy single-agent default until the
    `Agent.run` ↔ `decompose_and_run` integration is mature (M122f).
    """
    if force is not None:
        return force
    env = env_manager_mode()
    if env is not None:
        return env
    if use_heuristic_default:
        return needs_decomposition(prompt)
    return False


def run_with_manager_if_eligible(
    prompt: str,
    *,
    agent_factory: AgentFactory,
    direct_runner,
    force: bool | None = None,
    factory_kwargs: dict[str, Any] | None = None,
) -> str | None:
    """Either dispatch via the manager orchestrator or fall through
    to `direct_runner(prompt)`.

    `direct_runner` is a callable taking the prompt and returning
    either a string reply or None on error — the existing single-
    agent invocation. Pass any function with that shape; this seam
    doesn't import Agent / cli.run / daemon factory so it stays
    decoupled from those (which avoids the integration breaking
    every time the runtime layout shifts).

    Returns the user-facing text or None on failure. Errors are
    logged at INFO; the caller decides how to surface them.
    """
    if should_use_manager(prompt, force=force):
        result: ManagerRunResult = decompose_and_run(
            prompt,
            agent_factory=agent_factory,
            factory_kwargs=factory_kwargs,
        )
        if result.error:
            logger.info(
                "manager-spawn failed: %s; falling back to direct runner",
                result.error,
            )
            return direct_runner(prompt)
        return result.final_text
    return direct_runner(prompt)


__all__ = [
    "MANAGER_ENV",
    "env_manager_mode",
    "run_with_manager_if_eligible",
    "should_use_manager",
]
