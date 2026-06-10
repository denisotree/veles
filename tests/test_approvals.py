"""Tests for core/approval.py — Tier ε M73 audit log."""

from __future__ import annotations

import json
from pathlib import Path

from veles.core.approval import (
    APPROVALS_DIRNAME,
    ApprovalRecord,
    approvals_dir,
    list_approvals,
    record_approval,
)


def test_approvals_dir_helper(tmp_path: Path) -> None:
    state = tmp_path / ".veles"
    assert approvals_dir(state) == state / APPROVALS_DIRNAME


def test_record_writes_json_with_uuid_filename(tmp_path: Path) -> None:
    state = tmp_path / ".veles"
    rec = record_approval(state, tool_name="run_shell", rule="trust_ladder")
    files = list((state / APPROVALS_DIRNAME).iterdir())
    assert len(files) == 1
    assert files[0].name == f"{rec.approval_id}.json"
    assert files[0].suffix == ".json"


def test_record_fields_round_trip(tmp_path: Path) -> None:
    state = tmp_path / ".veles"
    rec = record_approval(
        state,
        tool_name="write_file",
        rule="always_confirm",
        via_autopilot=False,
        session_id="sess-42",
        reason="user confirmed",
        arguments={"path": "/tmp/x", "content": "hello"},
        scope="always-project",
    )
    saved = json.loads(
        (state / APPROVALS_DIRNAME / f"{rec.approval_id}.json").read_text()
    )
    assert saved["tool_name"] == "write_file"
    assert saved["rule"] == "always_confirm"
    assert saved["session_id"] == "sess-42"
    assert saved["scope"] == "always-project"
    assert saved["approver"] == "user"
    assert saved["arguments"] == {"path": "/tmp/x", "content": "hello"}


def test_via_autopilot_sets_approver_to_autopilot(tmp_path: Path) -> None:
    state = tmp_path / ".veles"
    record_approval(state, tool_name="t", rule="trust_ladder", via_autopilot=True)
    saved = json.loads(next((state / APPROVALS_DIRNAME).iterdir()).read_text())
    assert saved["approver"] == "autopilot"
    assert saved["via_autopilot"] is True


def test_list_approvals_sorted_by_decided_at(tmp_path: Path) -> None:
    state = tmp_path / ".veles"
    # decided_at granularity is 1s; force order via direct file write.
    (state / APPROVALS_DIRNAME).mkdir(parents=True)
    for i, ts in enumerate(["2026-05-01T00:00:00Z", "2026-04-01T00:00:00Z"]):
        (state / APPROVALS_DIRNAME / f"r{i}.json").write_text(
            json.dumps({"approval_id": f"r{i}", "decided_at": ts, "tool_name": "t"})
        )
    approvals = list_approvals(state)
    assert [r["decided_at"] for r in approvals] == [
        "2026-04-01T00:00:00Z",
        "2026-05-01T00:00:00Z",
    ]


def test_list_approvals_missing_dir(tmp_path: Path) -> None:
    assert list_approvals(tmp_path / "nope") == []


def test_list_approvals_skips_malformed_files(tmp_path: Path) -> None:
    state = tmp_path / ".veles"
    (state / APPROVALS_DIRNAME).mkdir(parents=True)
    (state / APPROVALS_DIRNAME / "broken.json").write_text("not json")
    (state / APPROVALS_DIRNAME / "ok.json").write_text(
        '{"approval_id":"ok","decided_at":"2026-01-01T00:00:00Z","tool_name":"t"}'
    )
    approvals = list_approvals(state)
    assert [r["approval_id"] for r in approvals] == ["ok"]


def test_approval_record_dataclass_defaults() -> None:
    rec = ApprovalRecord(
        approval_id="x",
        tool_name="t",
        action="dispatch t",
        decided_at="2026-01-01T00:00:00Z",
        rule="trust_ladder",
    )
    assert rec.approver == "user"
    assert rec.via_autopilot is False
    assert rec.scope == "once"
    assert rec.arguments == {}


def test_record_creates_parent_directories(tmp_path: Path) -> None:
    state = tmp_path / "a" / "b" / "c"
    # Parent does not exist yet — record_approval must create it.
    record_approval(state, tool_name="t", rule="trust_ladder")
    assert (state / APPROVALS_DIRNAME).exists()


def test_record_includes_action_label(tmp_path: Path) -> None:
    state = tmp_path / ".veles"
    rec = record_approval(state, tool_name="run_shell", rule="trust_ladder")
    assert rec.action == "dispatch run_shell"
    custom = record_approval(
        state, tool_name="foo", rule="trust_ladder", action="explicit-action"
    )
    assert custom.action == "explicit-action"
