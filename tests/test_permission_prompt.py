"""Tests for the unified PromptRequest/PromptAnswer shape and
`format_prompt_body` shared between TUI, CLI and Telegram surfaces."""

from __future__ import annotations

from veles.core.permission.prompt import (
    PromptAnswer,
    PromptRequest,
    format_prompt_body,
)


def _req(**overrides) -> PromptRequest:
    base = dict(
        tool_name="run_shell",
        arguments={"command": "ls -la /etc"},
        reason="process_execution requires trust ladder",
        kind="trust",
    )
    base.update(overrides)
    return PromptRequest(**base)  # type: ignore[arg-type]


def test_body_includes_tool_reason_and_args() -> None:
    body = format_prompt_body(_req())
    assert "Tool: run_shell" in body
    assert "Reason: process_execution requires trust ladder" in body
    assert "command: ls -la /etc" in body


def test_body_renders_empty_args_as_none() -> None:
    body = format_prompt_body(_req(arguments={}))
    assert "Arguments: (none)" in body


def test_body_truncates_long_scalar_with_total_count() -> None:
    huge = "x" * 2500
    body = format_prompt_body(
        _req(arguments={"payload": huge}), max_value_chars=200
    )
    assert "x" * 200 in body
    assert "total 2500 chars" in body
    # the raw 2500-char value should NOT appear in full
    assert "x" * 2500 not in body


def test_body_renders_dict_value_as_pretty_json() -> None:
    body = format_prompt_body(
        _req(arguments={"opts": {"recursive": True, "limit": 5}})
    )
    # JSON dump uses double-quoted keys
    assert '"recursive": true' in body
    assert '"limit": 5' in body


def test_body_handles_list_value() -> None:
    body = format_prompt_body(_req(arguments={"paths": ["a.txt", "b/c.md"]}))
    assert '"a.txt"' in body
    assert '"b/c.md"' in body


def test_body_falls_back_to_repr_for_non_json_value() -> None:
    class _Weird:
        def __repr__(self) -> str:
            return "<Weird()>"

    body = format_prompt_body(_req(arguments={"obj": _Weird()}))
    # JSON dump uses default=str fallback; either way, the body must
    # contain *something* identifiable rather than raise.
    assert "obj:" in body
    assert "Weird" in body


def test_reason_defaults_to_unspecified() -> None:
    body = format_prompt_body(_req(reason=""))
    assert "Reason: (unspecified)" in body


def test_answer_approved_flag_matches_decision() -> None:
    assert PromptAnswer("allow_once").approved is True
    assert PromptAnswer("allow_session").approved is True
    assert PromptAnswer("allow_project").approved is True
    assert PromptAnswer("allow_global").approved is True
    assert PromptAnswer("deny").approved is False
