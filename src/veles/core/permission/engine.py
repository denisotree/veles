"""Permission Engine — single decision-point for tool dispatch.

`evaluate(entry, args)` runs a fixed sequence of rules and returns a typed
`Decision`. The rules, in order:

  1. `module_veto`     — handled upstream in `agent._dispatch` (pre_tool_call
                         hook). Engine doesn't see it; veto returns before
                         we get here. Documented for completeness.
  2. `planning_mode`   — denies mutation tools in planning mode (M71).
  3. `draft_commit`    — denies commit tools whose draft hasn't run (M72).
  4. `untrusted_args`  — STUB. Once source-trust labels reach the engine,
                         blocks tool calls whose args derive from
                         untrusted content. Today: no-op.
  5. `_policy_gate`    — (M124-perm-unify) single gate consulting
                         `effective_policy(entry)`, which layers project /
                         user / builtin overrides on top of the M65 risk
                         floor. Routes to trust-ladder (M38) when the tool
                         is sensitive and policy=approval_required, to the
                         critical-ops prompt when policy=always_confirm,
                         to the M71 approval prompt when not sensitive,
                         or to allow otherwise. Both trust and approval
                         prompters now receive the tool's args so the UI
                         can show what the agent actually wants to do.

Source-of-truth for "did the user authorize this?" is the trust store,
populated by the existing M38 UI — the engine reads it through
`evaluate_trust`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from veles.core.agent_state import invoked_tools, is_planning
from veles.core.critical_ops import confirm_critical
from veles.core.permission.policy import effective_policy
from veles.core.risk import RiskClass, is_mutation_class
from veles.core.tools.registry import ToolEntry
from veles.core.trust import evaluate_trust

DecisionKind = Literal[
    "allow",
    "deny",
    "approval_required",
    "sandbox",
    "draft_only",
    "require_stronger_auth",
]


Rule = Literal[
    "module_veto",
    "planning_mode",
    "draft_commit",
    "untrusted_args",
    "always_confirm",
    "trust_ladder",
    "approval_prompt",
    "risk_default",
    "default_allow",
]


@dataclass(slots=True, frozen=True)
class Decision:
    """One Permission Engine outcome.

    `kind` is the typed decision. `rule` names the rule that produced it
    (machine-stable key — for trace / event-log filtering). `reason` is a
    one-liner safe to show the user. `via_autopilot` flags decisions that
    would have been blocking gates without an active autopilot window —
    the audit layer uses this to attribute risk after the fact.
    """

    kind: DecisionKind
    rule: Rule
    reason: str = ""
    via_autopilot: bool = False

    @property
    def allowed(self) -> bool:
        """True when the call may proceed."""
        return self.kind == "allow"


# ---- rule helpers (private) ----


def _planning_mode_rule(entry: ToolEntry) -> Decision | None:
    """Block mutation tools while the agent is in Planning state (M71).

    Planning is the explicit pre-commit phase: read, search, compute, draft.
    A mutation call here is either an attempt to skip the approval gate or
    a model mistake. Either way the engine surfaces the denial so the model
    sees a typed observation, not a silent skip.
    """
    rc = entry.risk_class
    if rc is None or not is_mutation_class(rc):
        return None
    if not is_planning():
        return None
    return Decision(
        kind="deny",
        rule="planning_mode",
        reason=(
            f"tool {entry.name!r} ({rc.value}) is blocked while in planning mode; "
            "exit planning to commit changes (switch with `/mode writing` or Shift+Tab — "
            "there is no `veles mode` command)"
        ),
    )


def _draft_commit_rule(entry: ToolEntry) -> Decision | None:
    """Pair draft↔commit: deny commit when its draft hasn't run yet (M72).

    A tool declared with `@tool(commit_of="draft_email")` is the commit
    half of a pair. The engine demands that `draft_email` has appeared
    in this session's tool-invocation set before the commit fires. This
    prevents the model from skipping the preview step on external
    sends, money moves, deletions — the cases best-practices §tools-and-permissions
    flags as requiring draft/commit separation.

    Returns None when the tool isn't a commit half (rule is a no-op for
    everyone else).
    """
    if entry.commit_of is None:
        return None
    if entry.commit_of in invoked_tools():
        return None
    return Decision(
        kind="deny",
        rule="draft_commit",
        reason=(
            f"{entry.name!r} is the commit half of a pair; call "
            f"{entry.commit_of!r} first to preview the action"
        ),
    )


# M198: egress tools whose argument is (or names) the destination data leaves
# by. A tool call to a host that appears in untrusted content read this run is
# the prompt-injection exfiltration signal we gate on.
_EGRESS_TOOLS = frozenset({"fetch_url", "web_search"})

# Domain-like host token: labels separated by dots ending in a 2+ char TLD.
_HOST_RE = re.compile(r"\b((?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,})\b", re.IGNORECASE)


def _untrusted_egress_host(args: dict[str, Any]) -> str | None:
    """Return a host in `args` that also appears in the run's untrusted corpus,
    or None. High-signal, low-false-positive: matches attacker-*named*
    destinations and verbatim host forwarding — not paraphrased/re-encoded
    exfil (a known gap; the model's own discretion + the boundary reminder
    remain the backstop there)."""
    from veles.core.agent_state import untrusted_corpus

    corpus = untrusted_corpus()
    if not corpus:
        return None
    corpus_l = "\n".join(corpus).lower()
    for value in args.values():
        if not isinstance(value, str):
            continue
        for match in _HOST_RE.finditer(value):
            host = match.group(1).lower()
            if len(host) >= 4 and host in corpus_l:
                return host
    return None


def _untrusted_args_rule(entry: ToolEntry, args: dict[str, Any]) -> Decision | None:
    """M198 (§8.6): gate an egress tool whose destination appears in untrusted
    content read earlier this run — the prompt-injection exfiltration signal.

    Forces a hard confirmation. Runs *before* `_policy_gate`, so the autopilot
    allow can't reach it; non-TTY `confirm_critical` refuses → fail-closed deny.
    Returns None (no gate) for non-egress tools or when no host overlaps.
    """
    if entry.name not in _EGRESS_TOOLS:
        return None
    host = _untrusted_egress_host(args)
    if host is None:
        return None
    ok = confirm_critical(
        f"dispatch {entry.name}",
        f"{entry.name!r} targets {host!r}, which appears in untrusted content read "
        f"this run — possible prompt-injection exfiltration.",
    )
    if ok:
        return Decision(
            kind="allow",
            rule="untrusted_args",
            reason="user confirmed untrusted-derived egress",
        )
    return Decision(
        kind="deny",
        rule="untrusted_args",
        reason=f"egress to {host!r} (from untrusted content) declined",
    )


def _policy_gate(entry: ToolEntry, args: dict[str, Any]) -> Decision:
    """M124-perm-unify: single gate consulting `effective_policy(entry)`.

    Replaces the previous trio (`_always_confirm_rule`, `_trust_ladder_rule`,
    `_risk_default_rule`). The policy resolver layers project / user /
    builtin overrides on top of the risk-class floor, and this rule
    converts that single string into one of three concrete paths:

      - `"allow"`             → Decision(allow) immediately.
      - `"always_confirm"`    → critical-ops prompt; allow or deny.
      - `"approval_required"` → trust-ladder path when `entry.sensitive`
        (M38: 4-option scoped persistence), otherwise the
        `approval_required` Decision that `agent._run_approval_prompt`
        consumes (M71: 2-option per-call).

    All paths propagate the tool's args to the prompter (M124 fix:
    "Tool 'run_shell' wants to execute" now shows the command).
    """

    policy = effective_policy(entry)
    rc = entry.risk_class

    if policy == "allow":
        reason = f"{rc.value}=allow (policy)" if rc is not None else "no risk metadata"
        return Decision(kind="allow", rule="risk_default", reason=reason)

    if policy == "always_confirm":
        summary = (
            f"{rc.value} action via tool {entry.name!r}"
            if rc is not None
            else f"tool {entry.name!r} requires always-confirm"
        )
        ok = confirm_critical(f"dispatch {entry.name}", summary)
        if ok:
            return Decision(
                kind="allow",
                rule="always_confirm",
                reason="confirmed by user",
            )
        return Decision(
            kind="deny",
            rule="always_confirm",
            reason="critical operation declined by user",
        )

    if policy == "approval_required":
        if entry.sensitive:
            td = evaluate_trust(
                entry.name,
                args,
                reason=f"{rc.value if rc else 'sensitive'} requires trust ladder",
            )
            kind: DecisionKind = "allow" if td.allowed else "deny"
            return Decision(
                kind=kind,
                rule="trust_ladder",
                reason=td.reason or "",
                via_autopilot=td.via_autopilot,
            )
        return Decision(
            kind="approval_required",
            rule="risk_default",
            reason=(
                f"{rc.value} requires approval"
                if rc is not None
                else f"tool {entry.name!r} requires approval"
            ),
        )

    # Unknown / typo'd policy — refuse safely so misconfig fails loud.
    return Decision(
        kind="deny",
        rule="risk_default",
        reason=f"unknown effective policy {policy!r}",
    )


# ---- public entry point ----


def evaluate(entry: ToolEntry, args: dict[str, Any]) -> Decision:
    """Decide whether `entry(*args)` may proceed. See module docstring."""
    d = _planning_mode_rule(entry)
    if d is not None:
        return d
    d = _draft_commit_rule(entry)
    if d is not None:
        return d
    d = _untrusted_args_rule(entry, args)
    if d is not None:
        return d
    return _policy_gate(entry, args)


# ---- decision -> event-log discriminator ----


def event_decision_str(d: Decision) -> str:
    """Render `d.kind` for the typed event log.

    Identity for now — kept as a function so that future log-schema tweaks
    (e.g. collapsing `sandbox` into `allow:sandbox`) live in one place.
    """
    return d.kind


__all__ = [
    "Decision",
    "DecisionKind",
    "Rule",
    "evaluate",
    "event_decision_str",
]


# Silence "unused" warnings on convenience imports kept for re-export.
_RC = RiskClass
