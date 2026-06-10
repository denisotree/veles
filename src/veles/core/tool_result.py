"""Structured tool result contract (Tier ε, M65).

Every tool that opts in returns a `ToolResult` instead of a bare `str`. The
model then has stable, machine-readable handles after a denial / error /
truncation, and the dispatch path can compare expected vs actual outcomes
for eval-grading (M70).

Legacy tools that still return `str` keep working — `Registry.dispatch`
auto-wraps them into `ToolResult(status="success", summary=<str>)`. Existing
text contract for the LLM is preserved by `serialize_for_dispatch`, which
renders a JSON line — modern providers parse this without any prompt-side
explanation.

Large outputs are truncated to `max_result_chars` and the full payload is
saved to `<project>/.veles/artifacts/<sha>.<ext>`, with `evidence_ref`
set to `artifact://veles/<sha>`. The model can fetch the artifact via a
follow-up `read_artifact` call (or just trust the summary) — either way
the prompt stays small.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

ARTIFACTS_DIR = "artifacts"
ARTIFACT_URI_PREFIX = "artifact://veles/"
DEFAULT_MAX_RESULT_CHARS = 8000
SUMMARY_MAX_CHARS = 500

ToolResultStatus = Literal[
    "success",
    "error",
    "denied",
    "timeout",
    "approval_required",
]


@dataclass(slots=True)
class ToolResult:
    """One structured observation returned by a tool to the model.

    Field semantics:
      status               — terminal state of the call (never `pending`).
      summary              — human-readable one-liner, ≤500 chars. Required.
                             Mandatory even on denial so the model sees *why*.
      data                 — structured payload (small). Truncated separately
                             from `summary` if oversized.
      evidence_ref         — `artifact://veles/<sha>` URI when the full
                             payload was offloaded to disk.
      next_valid_actions   — tool names that make sense to call after this
                             observation. Empty list means model decides.
      error_type           — machine-stable key for failures ("path_escape",
                             "rate_limited", "auth_expired", ...). None on
                             success.
    """

    status: ToolResultStatus
    summary: str
    data: dict[str, Any] | None = None
    evidence_ref: str | None = None
    next_valid_actions: list[str] = field(default_factory=list)
    error_type: str | None = None

    def __post_init__(self) -> None:
        if len(self.summary) > SUMMARY_MAX_CHARS:
            # Hard cap on summary — truncation is silent because the data
            # field is the right place for verbose detail.
            self.summary = self.summary[: SUMMARY_MAX_CHARS - 1] + "…"


def success(summary: str, **kw: Any) -> ToolResult:
    """Convenience constructor — most call sites prefer this over the dataclass."""
    return ToolResult(status="success", summary=summary, **kw)


def error(summary: str, *, error_type: str, **kw: Any) -> ToolResult:
    return ToolResult(status="error", summary=summary, error_type=error_type, **kw)


def denied(summary: str, *, error_type: str = "denied", **kw: Any) -> ToolResult:
    return ToolResult(status="denied", summary=summary, error_type=error_type, **kw)


# ---- artifact storage ----


def artifact_path(state_dir: Path, sha: str, *, ext: str = "txt") -> Path:
    """`<project>/.veles/artifacts/<sha>.<ext>` — canonical layout."""
    return state_dir / ARTIFACTS_DIR / f"{sha}.{ext}"


def store_artifact(state_dir: Path, payload: str | bytes, *, ext: str = "txt") -> str:
    """Persist `payload` under a content-addressed name. Returns the URI.

    Content-addressed by sha256 → repeated identical writes deduplicate.
    Falls back to writing nothing and returning a `data://` self-ref when
    `state_dir` is None or unavailable; the model still sees the structured
    summary in that case.
    """
    blob = payload.encode("utf-8") if isinstance(payload, str) else payload
    sha = hashlib.sha256(blob).hexdigest()[:32]
    path = artifact_path(state_dir, sha, ext=ext)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(blob)
    return f"{ARTIFACT_URI_PREFIX}{sha}"


def truncate_with_artifact(
    payload: str,
    *,
    max_chars: int,
    state_dir: Path | None,
    head_chars: int = 500,
    tail_chars: int = 500,
) -> tuple[str, str | None]:
    """Truncate `payload` to `max_chars` and offload the full text to an artifact.

    Returns `(visible_text, evidence_ref)`. When `payload` fits already, returns
    the original string and `None`. When the project's state_dir is unavailable
    we still truncate but skip the artifact write — eval mode and ad-hoc shells
    just get the head/tail preview.
    """
    if len(payload) <= max_chars:
        return payload, None
    evidence_ref: str | None = None
    if state_dir is not None:
        try:
            evidence_ref = store_artifact(state_dir, payload, ext="txt")
        except OSError:
            evidence_ref = None
    head = payload[:head_chars]
    tail = payload[-tail_chars:] if tail_chars > 0 else ""
    marker = (
        f"\n…[truncated {len(payload) - head_chars - tail_chars} chars; "
        f"full payload at {evidence_ref or '(artifact unavailable)'}]…\n"
    )
    visible = head + marker + tail
    return visible, evidence_ref


# ---- serialization to the dispatch wire format ----


def serialize_for_dispatch(result: ToolResult) -> str:
    """Render `result` to the JSON string the LLM sees as the tool's content.

    JSON is unambiguous, providers parse it as-is, and `next_valid_actions`
    survives the round trip — the model can chain to a sensible next call
    without re-derivation. Fields with falsy / empty values are omitted to
    keep the prompt compact and cache-friendly.
    """
    payload: dict[str, Any] = {"status": result.status, "summary": result.summary}
    if result.data is not None:
        payload["data"] = result.data
    if result.evidence_ref:
        payload["evidence_ref"] = result.evidence_ref
    if result.next_valid_actions:
        payload["next_valid_actions"] = list(result.next_valid_actions)
    if result.error_type:
        payload["error_type"] = result.error_type
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def to_dict(result: ToolResult) -> dict[str, Any]:
    """Dict form for typed event logs / trace records."""
    return asdict(result)
