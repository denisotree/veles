"""Tests for core/tool_result.py — Tier ε M65 structured tool contract."""

from __future__ import annotations

import json
from pathlib import Path

from veles.core.tool_result import (
    ARTIFACT_URI_PREFIX,
    DEFAULT_MAX_RESULT_CHARS,
    SUMMARY_MAX_CHARS,
    ToolResult,
    artifact_path,
    denied,
    error,
    serialize_for_dispatch,
    store_artifact,
    success,
    to_dict,
    truncate_with_artifact,
)


# ---------- ToolResult dataclass ----------


def test_factory_constructors_set_status() -> None:
    assert success("ok").status == "success"
    assert error("bad", error_type="rate_limited").status == "error"
    assert denied("blocked").status == "denied"


def test_summary_is_clipped_to_500_chars() -> None:
    long = "x" * 1000
    r = success(long)
    assert len(r.summary) <= SUMMARY_MAX_CHARS
    assert r.summary.endswith("…")


def test_to_dict_round_trip() -> None:
    r = ToolResult(
        status="success",
        summary="ok",
        data={"k": "v"},
        evidence_ref="artifact://veles/abc",
        next_valid_actions=["read_file"],
        error_type=None,
    )
    d = to_dict(r)
    assert d["status"] == "success"
    assert d["data"] == {"k": "v"}
    assert d["evidence_ref"] == "artifact://veles/abc"


# ---------- serialize_for_dispatch ----------


def test_serializer_omits_falsy_fields() -> None:
    r = success("ok")
    payload = json.loads(serialize_for_dispatch(r))
    assert payload == {"status": "success", "summary": "ok"}
    # `data`, `evidence_ref`, `next_valid_actions`, `error_type` are all
    # omitted because they're empty / None — prompt stays compact.
    assert "data" not in payload
    assert "evidence_ref" not in payload


def test_serializer_preserves_next_valid_actions() -> None:
    r = ToolResult(
        status="denied",
        summary="blocked",
        error_type="permission_denied",
        next_valid_actions=["request_approval", "draft_email"],
    )
    payload = json.loads(serialize_for_dispatch(r))
    assert payload["next_valid_actions"] == ["request_approval", "draft_email"]
    assert payload["error_type"] == "permission_denied"


def test_serializer_compact_no_spaces() -> None:
    """Compact separators keep token count predictable for prompt-cache stability."""
    s = serialize_for_dispatch(success("ok"))
    assert ", " not in s
    assert ": " not in s


# ---------- artifact storage ----------


def test_store_artifact_dedupes_by_content_hash(tmp_path: Path) -> None:
    state = tmp_path / ".veles"
    ref1 = store_artifact(state, "hello world")
    ref2 = store_artifact(state, "hello world")
    assert ref1 == ref2  # same content -> same URI
    files = list((state / "artifacts").iterdir())
    assert len(files) == 1


def test_store_artifact_different_content_different_uri(tmp_path: Path) -> None:
    state = tmp_path / ".veles"
    a = store_artifact(state, "alpha")
    b = store_artifact(state, "beta")
    assert a != b


def test_artifact_uri_prefix(tmp_path: Path) -> None:
    state = tmp_path / ".veles"
    ref = store_artifact(state, "x")
    assert ref.startswith(ARTIFACT_URI_PREFIX)


def test_artifact_path_helper(tmp_path: Path) -> None:
    state = tmp_path / ".veles"
    assert artifact_path(state, "abc123") == state / "artifacts" / "abc123.txt"


# ---------- truncate_with_artifact ----------


def test_truncate_passes_short_payload_through(tmp_path: Path) -> None:
    state = tmp_path / ".veles"
    visible, ref = truncate_with_artifact("hello", max_chars=100, state_dir=state)
    assert visible == "hello"
    assert ref is None


def test_truncate_offloads_long_payload_to_artifact(tmp_path: Path) -> None:
    state = tmp_path / ".veles"
    payload = "x" * 5000
    visible, ref = truncate_with_artifact(
        payload, max_chars=100, state_dir=state, head_chars=50, tail_chars=50
    )
    assert len(visible) < len(payload)
    assert ref is not None
    assert ref.startswith(ARTIFACT_URI_PREFIX)
    # Marker references the artifact for the model.
    assert ref in visible
    # Round-trip: artifact contains the original payload.
    sha = ref.removeprefix(ARTIFACT_URI_PREFIX)
    saved = (state / "artifacts" / f"{sha}.txt").read_text()
    assert saved == payload


def test_truncate_skips_artifact_when_no_state_dir(tmp_path: Path) -> None:
    payload = "x" * 5000
    visible, ref = truncate_with_artifact(payload, max_chars=100, state_dir=None)
    assert ref is None
    assert len(visible) < len(payload)
    # Falls back to a non-URI marker.
    assert "artifact unavailable" in visible


def test_default_max_result_chars_constant() -> None:
    assert DEFAULT_MAX_RESULT_CHARS == 8000
