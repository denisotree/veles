"""Tool risk taxonomy (Tier ε, M65).

Every tool that can side-effect must declare a `risk_class`. The class is
the only input the Permission Engine (M64, §15.0) needs from the tool
itself — everything else (path scope, project boundary, autopilot state)
comes from the runtime context.

The taxonomy below adds two Veles-specific splits to a standard
tool-permission model: `write_local_project` vs `write_local_user_global`
(scope matters for the M5+M37 sandbox), and the explicit `network_open_world`
class for any HTTP call beyond the chosen LLM endpoint.

`DEFAULT_POLICY` is the table the Permission Engine starts from. Project/user
trust-ladder rules (M38) and always-confirm checks (M39) layer on top and can
override `allow` to `approval_required`, never the reverse.
"""

from __future__ import annotations

import enum


class RiskClass(enum.Enum):
    # Read-side
    READ_ONLY = "read_only"
    SEARCH_ONLY = "search_only"
    COMPUTE_ONLY = "compute_only"  # sandboxed compute that never touches FS/net
    DRAFT_ONLY = "draft_only"  # prepares an artifact, never commits it

    # Write-side, local scope
    WRITE_LOCAL_PROJECT = "write_local_project"
    WRITE_LOCAL_USER_GLOBAL = "write_local_user_global"

    # Write-side, external scope
    WRITE_EXTERNAL = "write_external"
    NETWORK_OPEN_WORLD = "network_open_world"

    # Execution
    PROCESS_EXECUTION = "process_execution"

    # Hard guardrails
    DESTRUCTIVE = "destructive"
    PRIVILEGED_ADMIN = "privileged_admin"


# Default Permission Engine outcome per risk class. The engine still consults
# trust_ladder, path_guard, always_confirm, and untrusted-source guards in
# order — this map is the *floor*, not the final answer.
#
# Values mirror the typed PermissionDecision shape from §15.0:
#   "allow"               — proceed without prompting
#   "approval_required"   — pause loop, ask the user (trust-ladder UI today)
#   "always_confirm"      — never bypassable, even with autopilot
DEFAULT_POLICY: dict[RiskClass, str] = {
    RiskClass.READ_ONLY: "allow",
    RiskClass.SEARCH_ONLY: "allow",
    RiskClass.COMPUTE_ONLY: "allow",
    RiskClass.DRAFT_ONLY: "allow",
    RiskClass.WRITE_LOCAL_PROJECT: "allow",
    RiskClass.WRITE_LOCAL_USER_GLOBAL: "allow",
    RiskClass.WRITE_EXTERNAL: "approval_required",
    RiskClass.NETWORK_OPEN_WORLD: "approval_required",
    RiskClass.PROCESS_EXECUTION: "approval_required",
    RiskClass.DESTRUCTIVE: "always_confirm",
    RiskClass.PRIVILEGED_ADMIN: "always_confirm",
}


# Risk classes that should auto-flag `sensitive=True` on the legacy gate
# until M64 lands and the Permission Engine takes over fully.
_SENSITIVE_DEFAULTS: frozenset[RiskClass] = frozenset(
    {
        RiskClass.WRITE_EXTERNAL,
        RiskClass.NETWORK_OPEN_WORLD,
        RiskClass.PROCESS_EXECUTION,
        RiskClass.DESTRUCTIVE,
        RiskClass.PRIVILEGED_ADMIN,
    }
)


# Risk classes that *mutate* something — denied during Planning mode (M71).
# Read-side + draft-only stay visible so the agent can inspect, search,
# reason, and draft without committing.
_MUTATION_CLASSES: frozenset[RiskClass] = frozenset(
    {
        RiskClass.WRITE_LOCAL_PROJECT,
        RiskClass.WRITE_LOCAL_USER_GLOBAL,
        RiskClass.WRITE_EXTERNAL,
        RiskClass.NETWORK_OPEN_WORLD,
        RiskClass.PROCESS_EXECUTION,
        RiskClass.DESTRUCTIVE,
        RiskClass.PRIVILEGED_ADMIN,
    }
)


def is_sensitive_class(rc: RiskClass) -> bool:
    """True when this class requires the trust-ladder gate by default.

    Bridge between M37/M38 (`entry.sensitive`) and the new taxonomy. Once
    M64 ships, agent.py asks the Permission Engine directly and this helper
    becomes legacy.
    """
    return rc in _SENSITIVE_DEFAULTS


def default_decision(rc: RiskClass) -> str:
    """Permission Engine starting point for `rc`. See `DEFAULT_POLICY`."""
    return DEFAULT_POLICY[rc]


def is_mutation_class(rc: RiskClass) -> bool:
    """True when the class side-effects something (write, network, exec).

    Planning mode (M71) denies tools in this set so the agent can read,
    search, and draft freely but cannot commit until the plan is approved.
    """
    return rc in _MUTATION_CLASSES


# Retry policy hint per risk class (§20.4). Used opportunistically by the
# dispatch path / future Permission Engine — never as security boundary.
_AUTO_RETRY: frozenset[RiskClass] = frozenset(
    {
        RiskClass.READ_ONLY,
        RiskClass.SEARCH_ONLY,
        RiskClass.COMPUTE_ONLY,
        RiskClass.DRAFT_ONLY,
    }
)


def auto_retry_allowed(rc: RiskClass) -> bool:
    """True if transient failures may be auto-retried for this class.

    Destructive / external / privileged calls are never auto-retried;
    the user (or an explicit `idempotent=True` opt-in, later) is the
    only path to a second attempt.
    """
    return rc in _AUTO_RETRY
