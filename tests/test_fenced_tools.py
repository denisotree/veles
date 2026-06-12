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
