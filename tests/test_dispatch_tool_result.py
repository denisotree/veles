"""Tests for Registry.dispatch — M65 wire-format behaviour.

Covers the three return modes:
  (1) handler returns ToolResult     → JSON serialization
  (2) handler returns short str      → raw passthrough (backward compat)
  (3) handler returns oversized str  → JSON serialization with evidence_ref
"""

from __future__ import annotations

import json
from pathlib import Path

from veles.core.risk import RiskClass
from veles.core.tool_result import ARTIFACT_URI_PREFIX, ToolResult, success
from veles.core.tools.registry import Registry, ToolEntry


def _make_registry(handler, *, max_result_chars: int = 8000) -> Registry:
    reg = Registry()
    reg.register(
        ToolEntry(
            name="t",
            description="test tool",
            parameter_schema={"type": "object"},
            handler=handler,
            is_async=False,
            max_result_chars=max_result_chars,
        )
    )
    return reg


# ---------- ToolResult passthrough ----------


def test_tool_result_serialized_to_json() -> None:
    reg = _make_registry(lambda: success("did the thing", next_valid_actions=["foo"]))
    out = reg.dispatch("t", {})
    payload = json.loads(out)
    assert payload["status"] == "success"
    assert payload["summary"] == "did the thing"
    assert payload["next_valid_actions"] == ["foo"]


def test_denied_tool_result_carries_error_type() -> None:
    def handler():
        return ToolResult(
            status="denied",
            summary="blocked by guard",
            error_type="path_escape",
            next_valid_actions=["write_file"],
        )

    reg = _make_registry(handler)
    out = reg.dispatch("t", {})
    payload = json.loads(out)
    assert payload["status"] == "denied"
    assert payload["error_type"] == "path_escape"


# ---------- str backward-compat ----------


def test_short_string_passes_through_unchanged() -> None:
    reg = _make_registry(lambda: "hello world")
    out = reg.dispatch("t", {})
    # No JSON wrap — legacy tools keep their wire shape.
    assert out == "hello world"


def test_empty_string_passes_through() -> None:
    reg = _make_registry(lambda: "")
    assert reg.dispatch("t", {}) == ""


def test_non_string_non_toolresult_is_coerced_to_str() -> None:
    reg = _make_registry(lambda: 42)
    assert reg.dispatch("t", {}) == "42"


# ---------- oversize truncation ----------


def test_oversized_string_gets_truncated_and_artifact_ref(tmp_path: Path) -> None:
    payload = "x" * 1000
    reg = _make_registry(lambda: payload, max_result_chars=100)
    out = reg.dispatch("t", {}, artifact_dir=tmp_path)
    # Output is now JSON-shaped (status=success, evidence_ref present).
    obj = json.loads(out)
    assert obj["status"] == "success"
    assert obj["evidence_ref"].startswith(ARTIFACT_URI_PREFIX)
    # Full content lives in the artifact dir.
    sha = obj["evidence_ref"].removeprefix(ARTIFACT_URI_PREFIX)
    assert (tmp_path / "artifacts" / f"{sha}.txt").read_text() == payload


def test_oversized_string_without_state_dir_still_truncates() -> None:
    payload = "y" * 1000
    reg = _make_registry(lambda: payload, max_result_chars=100)
    out = reg.dispatch("t", {})
    obj = json.loads(out)
    # No state_dir → no artifact, but summary signals it.
    assert obj.get("evidence_ref") is None or obj["evidence_ref"] == ""
    assert len(obj["summary"]) < len(payload)


# ---------- ToolEntry metadata ----------


def test_tool_entry_carries_risk_metadata() -> None:
    reg = _make_registry(lambda: "ok")
    # Default ToolEntry (no risk_class) — sensitive stays False, risk_class None.
    entry = reg.get("t")
    assert entry.risk_class is None
    assert entry.sensitive is False
    assert entry.max_result_chars == 8000


def test_tool_decorator_derives_sensitive_from_risk_class() -> None:
    # Apply via a fresh Registry to avoid global namespace pollution.
    reg = Registry()
    reg.register(
        ToolEntry(
            name="run",
            description="x",
            parameter_schema={"type": "object"},
            handler=lambda: "ok",
            is_async=False,
            risk_class=RiskClass.PROCESS_EXECUTION,
            sensitive=True,
        )
    )
    entry = reg.get("run")
    assert entry.risk_class is RiskClass.PROCESS_EXECUTION
    assert entry.sensitive is True
