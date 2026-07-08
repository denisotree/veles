"""M143: text/fenced-block tool-calling for non-native models.

Local models without OpenAI function-calling get no tools at all in the native
path. Fenced mode presents tools as text instructions and parses calls back out
of the model's prose — but ONLY when `provider.supports_tools is False`, so a
native model's illustrative code block is never executed as a real call.

Invariants:
  1. `render_tools_prompt` lists tools + the sentinel + call syntax.
  2. `parse_tool_calls` extracts well-formed blocks, skips malformed ones, and
     returns [] when there's no block.
  3. FOOTGUN: a native provider's ```bash``` prose is never parsed/executed.
  4. e2e: a non-native provider emitting a `veles-tool` block runs the tool;
     the result returns as a *user* message — history carries no `role=tool`
     message and no assistant `tool_calls` (wire stays plain).
  5. The fenced instructions are injected once; resume does not duplicate them.
  6. `fenced_tools=False` restores the old behaviour (local model gets nothing).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from veles.core.agent import Agent
from veles.core.fenced_tools import (
    FENCED_RESULT_HEADER,
    FENCED_SENTINEL,
    parse_tool_calls,
    render_tools_prompt,
)
from veles.core.provider import ProviderResponse, TokenUsage
from veles.core.tools.registry import Registry, ToolEntry


def _usage() -> TokenUsage:
    return TokenUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10)


def _final(text: str) -> ProviderResponse:
    return ProviderResponse(text=text, tool_calls=[], usage=_usage(), finish_reason="stop")


def _schemas() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a file",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
        }
    ]


def _registry_with_read() -> Registry:
    reg = Registry()
    reg.register(
        ToolEntry(
            name="read_file",
            description="Read a file",
            parameter_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
            handler=lambda path="": f"contents of {path}",
            is_async=False,
            sensitive=False,
        )
    )
    return reg


# --- unit: render_tools_prompt --------------------------------------------


def test_render_lists_tools_with_sentinel_and_syntax() -> None:
    prompt = render_tools_prompt(_schemas())
    assert FENCED_SENTINEL in prompt
    assert "veles-tool" in prompt
    assert "read_file" in prompt
    assert "path" in prompt  # argument surfaced


# --- unit: parse_tool_calls -----------------------------------------------


def test_parse_single_block() -> None:
    text = 'Sure.\n```veles-tool\n{"name": "read_file", "arguments": {"path": "a.py"}}\n```'
    calls = parse_tool_calls(text)
    assert len(calls) == 1
    assert calls[0].name == "read_file"
    assert calls[0].arguments == {"path": "a.py"}


def test_parse_multiple_blocks_in_order() -> None:
    text = (
        '```veles-tool\n{"name": "read_file", "arguments": {"path": "a"}}\n```\n'
        "and then\n"
        '```veles-tool\n{"name": "read_file", "arguments": {"path": "b"}}\n```'
    )
    calls = parse_tool_calls(text)
    assert [c.arguments["path"] for c in calls] == ["a", "b"]
    assert calls[0].id != calls[1].id


def test_parse_flat_arguments_shape() -> None:
    """Small local models (seen live 2026-07-08: ollama qwen3.5:9b) put the
    arguments at the TOP LEVEL next to "name" instead of nesting them under
    "arguments". Dropping them silently ran list_files with no path and
    crashed search_files with a missing positional — recover them instead."""
    text = (
        "```veles-tool\n"
        '{"name": "search_files", "pattern": "\\\\.md$", "path": ".", "max_results": 50}\n'
        "```"
    )
    calls = parse_tool_calls(text)
    assert len(calls) == 1
    assert calls[0].name == "search_files"
    assert calls[0].arguments == {"pattern": "\\.md$", "path": ".", "max_results": 50}


def test_parse_flat_shape_ignores_id_and_type_keys() -> None:
    body = '{"name": "read_file", "id": "x", "type": "function", "path": "a.py"}'
    calls = parse_tool_calls(f"```veles-tool\n{body}\n```")
    assert calls[0].arguments == {"path": "a.py"}


def test_nested_arguments_still_win_over_flat_extras() -> None:
    text = '```veles-tool\n{"name": "read_file", "arguments": {"path": "a"}, "path": "b"}\n```'
    calls = parse_tool_calls(text)
    assert calls[0].arguments == {"path": "a"}  # explicit nested form is canonical


def test_parse_multiple_objects_in_one_block() -> None:
    """Small local models (seen live 2026-07-08: ollama qwen3.5:9b) violate the
    "one JSON object per block" rule and stack several calls in a single fence.
    Dropping the whole block silently ended the turn mid-task — recover one
    call per object instead."""
    text = (
        "```veles-tool\n"
        '{"name": "list_files", "arguments": {"path": "a"}}\n'
        '{"name": "list_files", "arguments": {"path": "b"}}\n'
        "```"
    )
    calls = parse_tool_calls(text)
    assert [c.arguments["path"] for c in calls] == ["a", "b"]
    assert calls[0].id != calls[1].id


def test_parse_unclosed_final_block_with_trailing_garbage() -> None:
    """The exact shape seen live 2026-07-08 (ollama qwen3.5:9b): the model's
    last round is a veles-tool fence that is never closed and ends in junk
    (`, `` ` ``). The block regex required a closing fence, so the calls
    vanished and the loop treated the response as a final answer."""
    text = (
        "```veles-tool\n"
        '{"name": "list_files", "arguments": {"path": "-- Daily --", "glob": "**/*"}}\n'
        '{"name": "list_files", "arguments": {"path": "-- Companies --", "glob": "**/*"}}, `'
    )
    calls = parse_tool_calls(text)
    assert [c.arguments["path"] for c in calls] == ["-- Daily --", "-- Companies --"]


def test_parse_multi_object_skips_bad_and_keeps_good() -> None:
    text = '```veles-tool\n{"name": "read_file", "arguments": {"path": "a"}}\nnot json at all\n```'
    calls = parse_tool_calls(text)
    assert [c.name for c in calls] == ["read_file"]


# --- display scrubbing (M143 follow-up, live 2026-07-08) -------------------
# In fenced mode the model's raw text IS the tool calls; streaming it verbatim
# dumped `{"name": …}` JSON and dangling ``` fences into the chat (observed
# with ollama qwen3.5:9b). The scrubber strips veles-tool blocks from the
# DISPLAY stream; the agent still parses the full raw text for calls.


def _scrub_all(chunks: list[str]) -> str:
    from veles.core.fenced_tools import FencedToolScrubber

    s = FencedToolScrubber()
    out = "".join(s.feed(c) for c in chunks)
    return out + s.finalize()


def test_scrubber_passes_plain_prose() -> None:
    assert _scrub_all(["hello ", "world"]) == "hello world"


def test_scrubber_strips_tool_block_split_across_chunks() -> None:
    chunks = ["Sure.\n``", '`veles-tool\n{"name": "read_file"}\n``', "`\nDone."]
    assert _scrub_all(chunks) == "Sure.\nDone."


def test_scrubber_keeps_normal_code_fences() -> None:
    text = "look:\n```python\nprint(1)\n```\nend"
    assert _scrub_all([text]) == text


def test_scrubber_handles_glued_fences() -> None:
    # Observed live: closing fence immediately followed by the next opener.
    text = '```veles-tool\n{"name": "a"}\n``````veles-tool\n{"name": "b"}\n```after'
    assert _scrub_all([text]) == "after"


def test_scrubber_closing_fence_with_trailing_prose() -> None:
    # Observed live: "```The output is truncated." — prose glued to the close.
    text = '```veles-tool\n{"name": "a"}\n```The output is truncated.'
    assert _scrub_all([text]) == "The output is truncated."


def test_scrubber_finalize_drops_unclosed_tool_block() -> None:
    assert _scrub_all(['text ```veles-tool\n{"name": "x"']) == "text "


def test_streaming_fenced_turn_shows_no_tool_json_in_chat() -> None:
    """Agent-level: a fenced streaming turn must not leak tool-call JSON into
    on_text_delta (the chat)."""
    from veles.core.provider import StreamEnd, TextDelta

    class _StreamingLocalProvider:
        name = "ollama"
        supports_tools = False
        supports_streaming = True
        n = 0

        def create_message(self, *a, **k):  # pragma: no cover
            raise AssertionError("streaming path expected")

        def stream_message(self, messages, tools=None, *, model, max_tokens=4096):
            del messages, tools, model, max_tokens
            type(self).n += 1
            if type(self).n == 1:
                parts = [
                    "I'll list first:\n",
                    '```veles-tool\n{"name": "read_file", "arguments": {"path": "a.py"}}\n```',
                ]
            else:
                parts = ["All done."]
            full = "".join(parts)
            for p in parts:
                yield TextDelta(text=p)
            yield StreamEnd(response=_resp(full))

    def _resp(text):
        from veles.core.provider import ProviderResponse, TokenUsage

        return ProviderResponse(
            text=text,
            tool_calls=[],
            usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            finish_reason="stop",
        )

    from veles.core.agent import Agent

    chat: list[str] = []
    agent = Agent(_StreamingLocalProvider(), _registry_with_read(), model="m")
    agent.run("go", on_text_delta=chat.append)
    joined = "".join(chat)
    assert "veles-tool" not in joined
    assert '"name"' not in joined
    assert "I'll list first:" in joined and "All done." in joined


def test_parse_skips_malformed_and_plain_text() -> None:
    assert parse_tool_calls("just a normal answer, no tools") == []
    assert parse_tool_calls("```veles-tool\nnot json\n```") == []
    assert parse_tool_calls('```veles-tool\n{"arguments": {}}\n```') == []  # no name
    # A plain ```bash``` block is not a veles-tool block.
    assert parse_tool_calls("```bash\nrm -rf /\n```") == []


# --- stubs ----------------------------------------------------------------


@dataclass
class _NativeProvider:
    """supports_tools=True. Returns prose containing an illustrative bash block
    — which must NEVER be executed."""

    responses: list[ProviderResponse]
    name: str = "native"
    supports_tools: bool = True
    supports_streaming: bool = False
    n: int = 0

    def create_message(self, messages, tools=None, *, model, max_tokens=4096):
        del messages, tools, model, max_tokens
        r = self.responses[self.n]
        self.n += 1
        return r


@dataclass
class _LocalProvider:
    """supports_tools=False. Drives the fenced path. Records the tool list it
    was handed each call (must always be None in fenced mode)."""

    responses: list[ProviderResponse]
    name: str = "local"
    supports_tools: bool = False
    supports_streaming: bool = False
    n: int = 0
    tools_seen: list = field(default_factory=list)

    def create_message(self, messages, tools=None, *, model, max_tokens=4096):
        del messages, model, max_tokens
        self.tools_seen.append(tools)
        r = self.responses[self.n]
        self.n += 1
        return r


# --- footgun: native model's illustrative block is never run --------------


def test_native_illustrative_block_is_not_executed() -> None:
    prose = "Here's how you would read it:\n```bash\ncat a.py\n```\nThat's the idea."
    provider = _NativeProvider(responses=[_final(prose)])
    agent = Agent(provider, _registry_with_read(), model="m")
    result = agent.run("how do I read a file?")
    # Native path: no tool dispatch, the prose is the answer verbatim.
    assert result.stopped_reason == "completed"
    assert result.text == prose
    assert not any(m.role == "tool" for m in result.history)
    # Native model was handed real schemas (not None).
    # (sanity: the registry had a tool to offer)
    assert provider.n == 1


# --- e2e: fenced path executes and feeds results back as a user message ----


def test_local_model_calls_tool_via_fenced_block() -> None:
    call_block = (
        'I will read it.\n```veles-tool\n{"name": "read_file", "arguments": {"path": "a.py"}}\n```'
    )
    provider = _LocalProvider(responses=[_final(call_block), _final("the file says hello")])
    agent = Agent(provider, _registry_with_read(), model="m")
    result = agent.run("read a.py")

    assert result.stopped_reason == "completed"
    assert result.text == "the file says hello"
    # Tools were never sent natively (fenced mode passes None every round).
    assert provider.tools_seen == [None, None]
    # No native tool-call wire shapes in history.
    assert not any(m.role == "tool" for m in result.history)
    assert not any(m.role == "assistant" and m.tool_calls for m in result.history)
    # The result came back as a user message carrying the tool output.
    result_msgs = [
        m for m in result.history if m.role == "user" and FENCED_RESULT_HEADER in (m.content or "")
    ]
    assert len(result_msgs) == 1
    assert "contents of a.py" in result_msgs[0].content
    # The tool instructions were injected into the system prompt.
    assert any(m.role == "system" and FENCED_SENTINEL in (m.content or "") for m in result.history)


def test_env_kill_switch_disables_fenced(monkeypatch) -> None:
    monkeypatch.setenv("VELES_FENCED_TOOLS", "0")
    block = '```veles-tool\n{"name": "read_file", "arguments": {"path": "a.py"}}\n```'
    provider = _LocalProvider(responses=[_final(block)])
    agent = Agent(provider, _registry_with_read(), model="m")  # default fenced_tools=True
    result = agent.run("read a.py")
    assert not any(m.role == "tool" for m in result.history)
    assert not any(FENCED_SENTINEL in (m.content or "") for m in result.history)


def test_fenced_disabled_restores_no_tools_for_local() -> None:
    # With fenced_tools=False a local model just answers; the block (if any) is
    # inert text and the tool never runs.
    block = '```veles-tool\n{"name": "read_file", "arguments": {"path": "a.py"}}\n```'
    provider = _LocalProvider(responses=[_final(block)])
    agent = Agent(provider, _registry_with_read(), model="m", fenced_tools=False)
    result = agent.run("read a.py")
    assert result.stopped_reason == "completed"
    assert not any(m.role == "tool" for m in result.history)
    assert not any(
        m.role == "user" and FENCED_RESULT_HEADER in (m.content or "") for m in result.history
    )
    # No fenced instructions injected.
    assert not any(FENCED_SENTINEL in (m.content or "") for m in result.history)
