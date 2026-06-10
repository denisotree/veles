"""Unified permission decisioning (Tier ε, M64).

`core.permission.engine` is the single decision-point for every tool call.
Until M64, M37 (path_guard), M38 (trust ladder), and M39 (always-confirm)
were stitched together inside `agent._dispatch` as scattered if-branches.
The engine consolidates them so:

  - the dispatch path has *one* call,
  - the decision is *typed*, comparable, and event-loggable,
  - new rules (untrusted-source guard, future M71 Planning-mode block)
    plug in without re-threading the call site.

Path-side enforcement still happens *inside* tools (`resolve_safe` etc.) —
the engine just orchestrates *user-facing* gates: trust ladder, autopilot,
always-confirm prompts, and the risk-class baseline from M65.
"""

from veles.core.permission.engine import (
    Decision,
    DecisionKind,
    Rule,
    evaluate,
)

__all__ = ["Decision", "DecisionKind", "Rule", "evaluate"]
