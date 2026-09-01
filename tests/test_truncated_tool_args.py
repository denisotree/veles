"""M240: a cut-off argument payload gets advice that can actually work.

Found on the first live GoalMode run (2026-09-01, `qwen/qwen3.8-27b` writing a
research report): the model called `write_file` with a long markdown body,
`Agent`'s default `max_tokens=4096` cut the completion mid-string,
`decode_tool_args` wrapped the fragment as `{"_raw": …}`, and the tool answered
"re-issue the call with a single well-formed JSON object". The model complied —
and hit the identical ceiling three times before giving up and pasting the
report into chat.

Truncation and a syntax slip are indistinguishable at the `{"_raw": …}`
boundary, but their remedies are opposite: retry vs. split. So classify.
"""

from __future__ import annotations

from veles.core.tool_args import decode_tool_args, looks_truncated, undecodable_args_error

# A realistic cut-off `write_file` payload: valid prefix, unterminated string.
_CUT_OFF = '{"path": "guimaraes.md", "content": "# Living in Guimaraes\\n\\n' + "word " * 60


def test_unterminated_string_reads_as_truncated() -> None:
    assert looks_truncated(_CUT_OFF) is True


def test_unclosed_brace_reads_as_truncated() -> None:
    payload = '{"path": "a.md", "meta": {"tags": ["x", "y"], "note": "' + "z" * 250 + '"'
    assert looks_truncated(payload) is True


def test_short_syntax_slip_is_not_truncation() -> None:
    """Genuine model typos are short; treating one as truncation would tell the
    model to split a payload that was never too big."""
    assert looks_truncated('{"path": "a.md",}') is False
    assert looks_truncated("not json at all") is False


def test_complete_json_is_not_truncation() -> None:
    assert looks_truncated('{"a": "' + "y" * 300 + '"}') is False


def test_non_object_payload_is_not_truncation() -> None:
    assert looks_truncated("y" * 500) is False
    assert looks_truncated(None) is False


def test_truncated_message_tells_the_model_to_split() -> None:
    msg = undecodable_args_error("write_file", _CUT_OFF)
    assert "cut off" in msg
    assert "Split the content across" in msg
    # The old advice must NOT appear — following it reproduces the failure.
    assert "re-issue the call" not in msg
    assert str(len(_CUT_OFF)) in msg, "the size is the actionable part"


def test_syntax_error_keeps_the_retry_advice() -> None:
    msg = undecodable_args_error("write_file", '{"path": "a.md",}')
    assert "not valid JSON" in msg
    assert "re-issue the call" in msg
    assert "cut off" not in msg


def test_registry_dispatch_uses_the_truncation_message() -> None:
    """End of the real path: `decode_tool_args` → `{"_raw": …}` → dispatch."""
    from veles.core.tools.registry import Registry, ToolEntry

    reg = Registry()
    reg.register(
        ToolEntry(
            name="write_file",
            description="",
            parameter_schema={"type": "object"},
            handler=lambda **_: "written",
            is_async=False,
            sensitive=False,
        )
    )
    args = decode_tool_args(_CUT_OFF)
    assert "_raw" in args, "the fragment must not decode"

    out = reg.dispatch("write_file", args)
    assert "cut off" in out
    assert "Split the content" in out
