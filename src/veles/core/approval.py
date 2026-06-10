"""Approval records (Tier ε, M73) — durable per-grant audit log.

`core/trust.py` + `trust_store.py` (M38) hold *rules*: "the user said yes
to `run_shell` for this project". That's good for "should I prompt the
next time?" but useless for "what did the agent actually do during
yesterday's autopilot window?".

This module fills the second question. Every time the Permission Engine
allows a tool dispatch through a user-facing gate (trust_ladder or
always_confirm), we write one JSON record to
`<project>/.veles/approvals/<uuid>.json`. Records are append-only and
content-addressable — neither the agent nor the curator rewrites them.

Audit query is just `cat <project>/.veles/approvals/*.json | jq ...`.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

APPROVALS_DIRNAME = "approvals"


@dataclass(slots=True, frozen=True)
class ApprovalRecord:
    """One grant of permission. Stored as a single JSON file.

    `approval_id`   — uuid4 hex; matches the file name (without `.json`).
    `tool_name`     — tool that was approved.
    `action`        — short, machine-stable label ("dispatch <tool>" today;
                      richer when M71 Planning lands).
    `decided_at`    — ISO-8601 UTC timestamp at engine decision time.
    `expires_at`    — optional ISO-8601 UTC; None = until-revoked.
    `approver`      — "user" by default; "autopilot" when the trust ladder
                      auto-allowed under an active autopilot window.
    `rule`          — which engine rule fired (`trust_ladder` /
                      `always_confirm`). Records for other rules are
                      not written.
    `via_autopilot` — true mirror of the engine's flag; redundant with
                      `approver` but keeps the jq queries trivial.
    `session_id`    — optional Veles session id for cross-ref into
                      `events.jsonl` (M69).
    `scope`         — free-form ("once", "always-project", future labels).
    `reason`        — short human-readable text from the decision.
    `evidence_ref`  — optional artifact URI showing what was approved.
    """

    approval_id: str
    tool_name: str
    action: str
    decided_at: str
    rule: str
    approver: str = "user"
    via_autopilot: bool = False
    expires_at: str | None = None
    session_id: str | None = None
    scope: str = "once"
    reason: str = ""
    evidence_ref: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)


def approvals_dir(state_dir: Path) -> Path:
    """`<state_dir>/approvals` — canonical location, created on demand."""
    return state_dir / APPROVALS_DIRNAME


def record_approval(
    state_dir: Path,
    *,
    tool_name: str,
    rule: str,
    via_autopilot: bool = False,
    session_id: str | None = None,
    reason: str = "",
    arguments: dict[str, Any] | None = None,
    scope: str = "once",
    expires_at: str | None = None,
    evidence_ref: str | None = None,
    action: str | None = None,
) -> ApprovalRecord:
    """Write one approval record and return it.

    Idempotent up to uuid collision (effectively never). Failures to write
    are surfaced as exceptions — the caller (agent dispatch) catches them
    so a broken approval log can never kill a run; tests catch them so
    silently dropped records get noticed.
    """
    approval_id = uuid.uuid4().hex
    record = ApprovalRecord(
        approval_id=approval_id,
        tool_name=tool_name,
        action=action or f"dispatch {tool_name}",
        decided_at=_now_iso(),
        rule=rule,
        approver="autopilot" if via_autopilot else "user",
        via_autopilot=via_autopilot,
        expires_at=expires_at,
        session_id=session_id,
        scope=scope,
        reason=reason,
        evidence_ref=evidence_ref,
        arguments=dict(arguments or {}),
    )
    target = approvals_dir(state_dir) / f"{approval_id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(asdict(record), ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return record


def list_approvals(state_dir: Path) -> list[dict[str, Any]]:
    """Read every record under `<state_dir>/approvals/`. Sorted by `decided_at`.

    Returns plain dicts so reader code is decoupled from future schema
    additions — keys appearing in newer records but not in this file's
    dataclass don't break anything.
    """
    d = approvals_dir(state_dir)
    if not d.exists():
        return []
    out: list[dict[str, Any]] = []
    for f in d.iterdir():
        if not f.is_file() or f.suffix != ".json":
            continue
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    out.sort(key=lambda r: r.get("decided_at", ""))
    return out


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
