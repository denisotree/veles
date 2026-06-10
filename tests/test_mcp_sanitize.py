"""M157 — untrusted MCP schema sanitization tests."""

from __future__ import annotations

from veles.mcp.sanitize import (
    MAX_PARAMS_PER_TOOL,
    MAX_TEXT_CHARS,
    normalize_tool_name,
    sanitize_schema,
    sanitize_text,
)

# ---- sanitize_text ----


def test_text_strips_control_chars_and_newlines() -> None:
    assert sanitize_text("a\x00b\ncd\te\x7ff") == "a b cd e f"


def test_text_collapses_whitespace() -> None:
    assert sanitize_text("  spaced    out   ") == "spaced out"


def test_text_truncates_with_ellipsis() -> None:
    out = sanitize_text("x" * 1000)
    assert len(out) <= MAX_TEXT_CHARS
    assert out.endswith("…")


def test_text_short_passthrough() -> None:
    assert sanitize_text("plain description.") == "plain description."


# ---- normalize_tool_name ----


def test_name_valid_passthrough() -> None:
    assert normalize_tool_name("list_issues-2") == "list_issues-2"


def test_name_strips_control_chars() -> None:
    assert normalize_tool_name("  echo\x00 ") == "echo"


def test_name_rejects_spaces_and_specials() -> None:
    assert normalize_tool_name("rm -rf /") is None
    assert normalize_tool_name("инструмент") is None
    assert normalize_tool_name("a.b") is None


def test_name_rejects_empty_and_oversized() -> None:
    assert normalize_tool_name("") is None
    assert normalize_tool_name("x" * 65) is None
    assert normalize_tool_name("x" * 64) == "x" * 64


# ---- sanitize_schema ----


def test_schema_non_dict_becomes_empty_object() -> None:
    assert sanitize_schema(None) == {"type": "object", "properties": {}}
    assert sanitize_schema("nope") == {"type": "object", "properties": {}}
    assert sanitize_schema([1, 2]) == {"type": "object", "properties": {}}


def test_schema_caps_param_count() -> None:
    props = {f"p{i}": {"type": "string"} for i in range(40)}
    out = sanitize_schema({"type": "object", "properties": props})
    assert len(out["properties"]) == MAX_PARAMS_PER_TOOL


def test_schema_drops_oversized_param_names() -> None:
    out = sanitize_schema(
        {"properties": {"ok": {"type": "string"}, "y" * 65: {"type": "string"}}}
    )
    assert set(out["properties"]) == {"ok"}


def test_schema_drops_unsafe_param_names() -> None:
    out = sanitize_schema(
        {"properties": {"with space": {}, "ctrl\x01": {}, "fine_name": {}}}
    )
    assert set(out["properties"]) == {"fine_name"}


def test_schema_truncates_property_descriptions() -> None:
    out = sanitize_schema(
        {"properties": {"p": {"type": "string", "description": "d" * 999}}}
    )
    desc = out["properties"]["p"]["description"]
    assert len(desc) <= MAX_TEXT_CHARS
    assert desc.endswith("…")


def test_schema_filters_required_to_surviving_params() -> None:
    out = sanitize_schema(
        {
            "properties": {"keep": {"type": "string"}, "bad name": {}},
            "required": ["keep", "bad name", "ghost"],
        }
    )
    assert out["required"] == ["keep"]


def test_schema_drops_non_dict_property_values() -> None:
    out = sanitize_schema({"properties": {"p": "stringy"}})
    assert out["properties"]["p"] == {}


def test_schema_strips_unknown_property_keys() -> None:
    out = sanitize_schema(
        {"properties": {"p": {"type": "integer", "x-evil": "payload", "default": 3}}}
    )
    assert out["properties"]["p"] == {"type": "integer", "default": 3}
