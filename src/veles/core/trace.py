"""Per-call trace + cache telemetry (Tier ε, M68).

Without observability every other Tier ε milestone debugs blind. This module
captures one JSON record per model call: provider, model, token split (incl.
cache_read / cache_creation), latency, hashes of the stable prompt prefix and
tool bundle, plus a final-status summary.

Records land in `<project>/.veles/traces.jsonl` (append-only, rotated when the
file grows past `max_bytes`). The trace writer is intentionally a no-op when
no active project is set (e.g. unit tests, ad-hoc shells), so wiring it in
never breaks call sites that didn't expect persistence.

Cache-fragmentation alert: scans recent records and flags a run where
`cache_read_tokens == 0` for >= `min_streak` turns despite a stable
`system_prompt_hash`. Surfaced as a function, not a daemon — callable from
curator, CLI, or a future `veles stats` command.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_MAX_BYTES = 50 * 1024 * 1024  # 50 MB before rotation
TRACE_FILENAME = "traces.jsonl"


@dataclass(slots=True)
class TraceRecord:
    """One row of `traces.jsonl`. All fields are JSON-serializable primitives."""

    request_id: str
    session_id: str | None
    ts: str  # ISO-8601 UTC, generated at call site
    provider: str
    model: str
    system_prompt_hash: str  # sha256:<hex> over the stable system-prompt text
    tool_bundle_hash: str  # sha256:<hex> over deterministically-serialized tools
    input_tokens_new: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    output_tokens: int = 0
    ttft_ms: int = 0  # 0 when not streaming
    total_latency_ms: int = 0
    est_cost_usd: float = 0.0
    tool_calls_count: int = 0
    permission_decisions: list[dict[str, Any]] = field(default_factory=list)
    final_status: str = "ok"  # ok | error | approval_pending | budget_exceeded | denied


def hash_text(text: str | None) -> str:
    """sha256(text) prefixed with `sha256:`. Stable across runs."""
    if not text:
        return "sha256:" + hashlib.sha256(b"").hexdigest()
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_tools(tools: list[dict[str, Any]] | None) -> str:
    """sha256 of tools serialized with sorted keys + sorted by tool name.

    Determinism here matters more than human-readability — two functionally
    identical tool bundles must hash identically across runs, otherwise the
    fragmentation detector sees ghost-drift.
    """
    if not tools:
        return "sha256:" + hashlib.sha256(b"[]").hexdigest()
    sorted_tools = sorted(tools, key=lambda t: _tool_name(t))
    canonical = json.dumps(sorted_tools, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _tool_name(tool: dict[str, Any]) -> str:
    # OpenAI shape: {"type":"function","function":{"name":..., ...}}
    # Native shape: {"name":..., ...}
    if "function" in tool and isinstance(tool["function"], dict):
        return str(tool["function"].get("name", ""))
    return str(tool.get("name", ""))


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class TraceWriter:
    """Append `TraceRecord`s to a JSONL file with size-bounded rotation.

    On rotation: existing file is renamed to `traces.jsonl.<unix_ts>` and a
    fresh `traces.jsonl` starts. We keep all rotated files (no auto-prune) —
    cleanup is a curator concern, not this writer's.
    """

    def __init__(self, path: Path, *, max_bytes: int = DEFAULT_MAX_BYTES) -> None:
        self._path = path
        self._max_bytes = max_bytes
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def write(self, record: TraceRecord) -> None:
        line = json.dumps(asdict(record), separators=(",", ":")) + "\n"
        data = line.encode("utf-8")
        if self._path.exists() and self._path.stat().st_size + len(data) > self._max_bytes:
            self._rotate()
        with self._path.open("ab") as f:
            f.write(data)

    def _rotate(self) -> None:
        ts = int(time.time())
        target = self._path.with_name(f"{self._path.name}.{ts}")
        # If a rotation already happened this same second, fall back to a counter.
        n = 1
        while target.exists():
            target = self._path.with_name(f"{self._path.name}.{ts}.{n}")
            n += 1
        os.replace(self._path, target)


def trace_path_for_project(state_dir: Path) -> Path:
    """`<project>/.veles/traces.jsonl` — the canonical location."""
    return state_dir / TRACE_FILENAME


def read_records(path: Path) -> list[dict[str, Any]]:
    """Read all records from a trace file. Used by alerts and tests.

    Skips malformed lines silently (operational tolerance — partial writes
    after a crash should not poison the whole file).
    """
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def cache_fragmentation_alert(
    records: list[dict[str, Any]],
    *,
    min_streak: int = 5,
) -> dict[str, Any] | None:
    """Detect a stable-prefix run where cache_read_tokens is 0 for too long.

    Returns a dict with diagnostic context if the alert fires, else None.
    Semantics: look at the trailing window. If the last `min_streak` records
    all share the same `system_prompt_hash` AND all have
    `cache_read_tokens == 0`, that's a fragmentation signal — either the
    cache_hints are broken, the provider isn't caching, or some upstream
    rewrite is invalidating the prefix.

    Records older than the trailing streak are ignored; we don't want a fresh
    `system_prompt_hash` change to mask a current problem.
    """
    if len(records) < min_streak:
        return None
    tail = records[-min_streak:]
    hashes = {r.get("system_prompt_hash") for r in tail}
    if len(hashes) != 1 or None in hashes:
        return None
    if not all(r.get("cache_read_tokens", 0) == 0 for r in tail):
        return None
    models = sorted({str(r["model"]) for r in tail if r.get("model")})
    providers = sorted({str(r["provider"]) for r in tail if r.get("provider")})
    return {
        "alert": "cache_fragmentation",
        "streak": min_streak,
        "system_prompt_hash": tail[0].get("system_prompt_hash"),
        "models": models,
        "providers": providers,
    }
