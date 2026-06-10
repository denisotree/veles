"""Effective-policy resolver for the Permission Engine (M124-perm-unify).

`DEFAULT_POLICY` in `core/risk.py` maps every `RiskClass` to one of
`"allow" | "approval_required" | "always_confirm"`. That's the *risk
floor* — it can never be lowered for destructive / privileged classes,
and it's the fallback when no other policy fires.

On top of the floor, three override layers stack (highest priority first):

  1. **Project config** — `<project>/.veles/config.toml`:
         [permissions]
         fetch_url   = "approval_required"
         write_file  = "always_confirm"
  2. **User config** — `~/.veles/config.toml`, same `[permissions]` shape.
  3. **Builtin overrides** — `BUILTIN_TOOL_POLICY_OVERRIDES` below: the
     project's opinionated defaults for read/search/fetch tools so
     `read_file`, `search_files`, `list_files`, `stat_file`, `web_search`,
     `fetch_url` don't pester the user every call.

The resolver lives here so every consumer (engine, tests, future CLI
inspectors) goes through the same code path. UI surfaces should *never*
read `DEFAULT_POLICY` directly — that bypasses the override stack.
"""

from __future__ import annotations

import logging
from typing import Final

from veles.core.context import current_project
from veles.core.project_config import get_section, load_project_config
from veles.core.risk import DEFAULT_POLICY, RiskClass
from veles.core.tools.registry import ToolEntry
from veles.core.user_config import get_user_section

logger = logging.getLogger(__name__)

VALID_POLICIES: Final[frozenset[str]] = frozenset(
    {"allow", "approval_required", "always_confirm"}
)


BUILTIN_TOOL_POLICY_OVERRIDES: Final[dict[str, str]] = {
    # Read-side tools — risk class is already READ_ONLY/SEARCH_ONLY ⇒
    # default-allow. We list them explicitly so a future risk-class
    # re-classification can't silently demote them.
    "read_file": "allow",
    "search_files": "allow",
    "list_files": "allow",
    "stat_file": "allow",
    # Network read — semantically search/lookup, not mutation. Default
    # changes from `NETWORK_OPEN_WORLD → approval_required` to `allow`
    # per user request; can be tightened in project / user [permissions].
    "web_search": "allow",
    "fetch_url": "allow",
}


# Risk classes whose floor must not be lowered (DESTRUCTIVE / PRIVILEGED_ADMIN
# default to `always_confirm`). Any project / user / builtin override that
# tries to ratchet these down to `allow` is logged and ignored.
_NEVER_LOWER_FLOOR_CLASSES: Final[frozenset[RiskClass]] = frozenset(
    {RiskClass.DESTRUCTIVE, RiskClass.PRIVILEGED_ADMIN}
)


def effective_policy(entry: ToolEntry) -> str:
    """Resolve the engine's policy for `entry`.

    Returns one of `"allow" | "approval_required" | "always_confirm"`.
    Never raises; invalid config values are logged and skipped so a
    typo doesn't break dispatch.

    Resolution order (first valid value wins):
      1. project [permissions]
      2. user    [permissions]
      3. BUILTIN_TOOL_POLICY_OVERRIDES
      4. risk_class floor from `risk.DEFAULT_POLICY`, then
         `entry.sensitive` ratchet (M38 legacy invariant: a tool flagged
         `sensitive=True` must always pass at least the trust ladder
         even when its risk class would otherwise default to allow —
         e.g. `write_file` is WRITE_LOCAL_PROJECT=allow but the user
         must consent before each new project).

    The sensitive-ratchet applies *only* to the implicit floor — an
    explicit user/project override on a `sensitive=True` tool still
    wins (lets the user opt write_file into auto-allow if they really
    want to). The destructive-floor invariant still prevents lowering
    DESTRUCTIVE / PRIVILEGED_ADMIN below `always_confirm`.
    """

    risk_floor = _risk_floor(entry)

    project_override = _read_project_override(entry.name)
    user_override = _read_user_override(entry.name)
    builtin_override = BUILTIN_TOOL_POLICY_OVERRIDES.get(entry.name)

    for source, value in (
        ("project", project_override),
        ("user", user_override),
        ("builtin", builtin_override),
    ):
        if value is None:
            continue
        if value not in VALID_POLICIES:
            logger.warning(
                "permissions override [%s] for tool %r ignored: invalid "
                "value %r (expected one of %s)",
                source,
                entry.name,
                value,
                sorted(VALID_POLICIES),
            )
            continue
        if _violates_floor(entry, value):
            logger.warning(
                "permissions override [%s] for tool %r tried to lower "
                "risk floor (%s → %s); ignored",
                source,
                entry.name,
                risk_floor,
                value,
            )
            continue
        return value

    # No override fired — apply the implicit ratchet for sensitive=True.
    if entry.sensitive and risk_floor == "allow":
        return "approval_required"
    return risk_floor


# ---- internals ----


def _risk_floor(entry: ToolEntry) -> str:
    if entry.risk_class is None:
        return "allow"
    return DEFAULT_POLICY.get(entry.risk_class, "approval_required")


def _violates_floor(entry: ToolEntry, candidate: str) -> bool:
    """True when `candidate` ratchets `entry`'s floor down.

    Currently the only ratchet we forbid is lowering DESTRUCTIVE /
    PRIVILEGED_ADMIN below `always_confirm`. Everything else is a
    legitimate user choice (e.g. tightening fetch_url back to
    `approval_required`).
    """

    rc = entry.risk_class
    if rc is None:
        return False
    if rc in _NEVER_LOWER_FLOOR_CLASSES and candidate != "always_confirm":
        return True
    return False


def _read_project_override(tool_name: str) -> str | None:
    project = current_project()
    if project is None:
        return None
    section = get_section(load_project_config(project), "permissions")
    val = section.get(tool_name)
    return val if isinstance(val, str) else None


def _read_user_override(tool_name: str) -> str | None:
    section = get_user_section("permissions")
    val = section.get(tool_name)
    return val if isinstance(val, str) else None


__all__ = [
    "BUILTIN_TOOL_POLICY_OVERRIDES",
    "VALID_POLICIES",
    "effective_policy",
]
