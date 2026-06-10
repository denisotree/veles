"""Integration tests: agent fires module hooks around turns and tool calls."""

from __future__ import annotations

from typing import Any

import pytest

from tests.conftest import StubProvider as _StubProvider
from veles.core.agent import Agent
from veles.core.modules import (
    ModuleRegistry,
    VetoResult,
    reset_module_registry,
    set_module_registry,
)
from veles.core.provider import ProviderResponse, TokenUsage, ToolCall
from veles.core.tools.registry import Registry, ToolEntry


def _ok_response(text: str = "done") -> ProviderResponse:
    return ProviderResponse(
        text=text,
        tool_calls=[],
        usage=TokenUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
        finish_reason="stop",
    )


def _tool_call_response(name: str, args: dict[str, Any]) -> ProviderResponse:
    return ProviderResponse(
        text=None,
        tool_calls=[ToolCall(id="c1", name=name, arguments=args)],
        usage=TokenUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
        finish_reason="tool_use",
    )


def _make_registry_with_echo() -> Registry:
    reg = Registry()
    reg.register(
        ToolEntry(
            name="echo",
            description="Echo input",
            parameter_schema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
            },
            handler=lambda text="": text,
            is_async=False,
        )
    )
    return reg


def test_agent_fires_pre_post_turn_hooks() -> None:
    seen: list[tuple[str, dict[str, Any]]] = []
    reg = ModuleRegistry()
    reg.add_hook("pre_turn", "x", lambda ctx: seen.append(("pre", ctx)))
    reg.add_hook("post_turn", "x", lambda ctx: seen.append(("post", ctx)))

    provider = _StubProvider(responses=[_ok_response("hi")])
    agent = Agent(provider=provider, registry=Registry(), model="m")

    token = set_module_registry(reg)
    try:
        result = agent.run("hello")
    finally:
        reset_module_registry(token)

    assert result.stopped_reason == "completed"
    kinds = [k for k, _ in seen]
    assert kinds == ["pre", "post"]
    pre_ctx = seen[0][1]
    assert pre_ctx["turn"] == 1
    assert pre_ctx["user_msg"] == "hello"
    post_ctx = seen[1][1]
    assert post_ctx["response_text"] == "hi"
    assert post_ctx["tokens_used"] == 20
    assert post_ctx["tool_call_count"] == 0


def test_agent_fires_pre_post_tool_call_hooks() -> None:
    seen: list[tuple[str, dict[str, Any]]] = []
    reg = ModuleRegistry()
    reg.add_hook("pre_tool_call", "x", lambda ctx: seen.append(("pre_tool", ctx)))
    reg.add_hook("post_tool_call", "x", lambda ctx: seen.append(("post_tool", ctx)))

    provider = _StubProvider(
        responses=[
            _tool_call_response("echo", {"text": "hi"}),
            _ok_response("final"),
        ]
    )
    agent = Agent(provider=provider, registry=_make_registry_with_echo(), model="m")

    token = set_module_registry(reg)
    try:
        agent.run("please echo hi")
    finally:
        reset_module_registry(token)

    kinds = [k for k, _ in seen]
    assert kinds == ["pre_tool", "post_tool"]
    pre_ctx = seen[0][1]
    assert pre_ctx == {"name": "echo", "arguments": {"text": "hi"}}
    post_ctx = seen[1][1]
    assert post_ctx["name"] == "echo"
    assert post_ctx["output"] == "hi"
    assert post_ctx["error"] is None


def test_post_tool_call_reports_error_on_dispatch_failure() -> None:
    seen: list[dict[str, Any]] = []
    reg = ModuleRegistry()
    reg.add_hook("post_tool_call", "x", lambda ctx: seen.append(ctx))

    boom_registry = Registry()

    def raises(**_kw):
        raise ValueError("nope")

    boom_registry.register(
        ToolEntry(
            name="boom",
            description="Always raises",
            parameter_schema={"type": "object", "properties": {}},
            handler=raises,
            is_async=False,
        )
    )
    provider = _StubProvider(
        responses=[
            _tool_call_response("boom", {}),
            _ok_response("recovered"),
        ]
    )
    agent = Agent(provider=provider, registry=boom_registry, model="m")

    token = set_module_registry(reg)
    try:
        agent.run("call boom")
    finally:
        reset_module_registry(token)

    assert len(seen) == 1
    ctx = seen[0]
    assert ctx["name"] == "boom"
    assert ctx["error"] is not None
    assert "ValueError" in ctx["error"]
    assert "<error" in ctx["output"]


def test_failing_hook_does_not_break_agent_loop(
    capsys: pytest.CaptureFixture[str],
) -> None:
    reg = ModuleRegistry()

    def boom(ctx):
        raise RuntimeError("hook is broken")

    reg.add_hook("pre_turn", "bad", boom)
    provider = _StubProvider(responses=[_ok_response("ok")])
    agent = Agent(provider=provider, registry=Registry(), model="m")

    token = set_module_registry(reg)
    try:
        result = agent.run("hi")
    finally:
        reset_module_registry(token)

    assert result.stopped_reason == "completed"
    assert result.text == "ok"
    err = capsys.readouterr().err
    assert "hook is broken" in err


def test_hooks_silent_when_module_registry_is_none() -> None:
    # No registry set; agent should still work normally.
    provider = _StubProvider(responses=[_ok_response("ok")])
    agent = Agent(provider=provider, registry=Registry(), model="m")
    result = agent.run("hi")
    assert result.text == "ok"


# ---- M26: pre_tool_call veto ----


def test_pre_tool_call_veto_blocks_handler_dispatch() -> None:
    """Module-vetoed tool call returns synthetic error without invoking handler."""
    handler_calls: list[dict[str, Any]] = []

    def echo_handler(text: str = "") -> str:
        handler_calls.append({"text": text})
        return text

    reg = Registry()
    reg.register(
        ToolEntry(
            name="echo",
            description="Echo input",
            parameter_schema={"type": "object", "properties": {"text": {"type": "string"}}},
            handler=echo_handler,
            is_async=False,
        )
    )

    mod_reg = ModuleRegistry()
    mod_reg.add_hook("pre_tool_call", "guard", lambda ctx: VetoResult(reason="echo is forbidden"))

    provider = _StubProvider(
        responses=[_tool_call_response("echo", {"text": "hi"}), _ok_response("recovered")]
    )
    agent = Agent(provider=provider, registry=reg, model="m")

    token = set_module_registry(mod_reg)
    try:
        result = agent.run("please echo")
    finally:
        reset_module_registry(token)

    assert result.stopped_reason == "completed"
    assert handler_calls == []  # handler never ran
    tool_msgs = [m for m in result.history if m.role == "tool"]
    assert len(tool_msgs) == 1
    body = tool_msgs[0].content or ""
    assert "vetoed by module 'guard'" in body
    assert "echo is forbidden" in body


def test_post_tool_call_observes_veto_with_error_field() -> None:
    seen_post: list[dict[str, Any]] = []
    mod_reg = ModuleRegistry()
    mod_reg.add_hook("pre_tool_call", "guard", lambda ctx: VetoResult(reason="not allowed"))
    mod_reg.add_hook("post_tool_call", "logger", lambda ctx: seen_post.append(ctx))

    provider = _StubProvider(
        responses=[_tool_call_response("echo", {"text": "x"}), _ok_response("done")]
    )
    agent = Agent(provider=provider, registry=_make_registry_with_echo(), model="m")

    token = set_module_registry(mod_reg)
    try:
        agent.run("please echo")
    finally:
        reset_module_registry(token)

    assert len(seen_post) == 1
    ctx = seen_post[0]
    assert ctx["name"] == "echo"
    assert ctx["error"] is not None
    assert "vetoed by guard" in ctx["error"]
    assert "not allowed" in ctx["error"]
    assert "vetoed" in ctx["output"]


def test_first_veto_wins_when_multiple_modules_register() -> None:
    mod_reg = ModuleRegistry()
    mod_reg.add_hook("pre_tool_call", "first", lambda ctx: VetoResult(reason="A"))
    mod_reg.add_hook("pre_tool_call", "second", lambda ctx: VetoResult(reason="B"))

    provider = _StubProvider(
        responses=[_tool_call_response("echo", {"text": "x"}), _ok_response("done")]
    )
    agent = Agent(provider=provider, registry=_make_registry_with_echo(), model="m")

    token = set_module_registry(mod_reg)
    try:
        result = agent.run("hi")
    finally:
        reset_module_registry(token)

    tool_msg = next(m for m in result.history if m.role == "tool")
    body = tool_msg.content or ""
    assert "module 'first'" in body
    assert "A" in body
    assert "B" not in body


# ---- M26: on_session_start / on_session_end ----


def test_on_session_start_fires_once_per_run() -> None:
    seen: list[dict[str, Any]] = []
    mod_reg = ModuleRegistry()
    mod_reg.add_hook("on_session_start", "x", lambda ctx: seen.append(ctx))

    provider = _StubProvider(responses=[_ok_response("ok")])
    agent = Agent(provider=provider, registry=Registry(), model="m")

    token = set_module_registry(mod_reg)
    try:
        agent.run("hi")
    finally:
        reset_module_registry(token)

    assert len(seen) == 1
    assert seen[0]["is_resume"] is False


def test_on_session_end_fires_on_completion() -> None:
    seen: list[dict[str, Any]] = []
    mod_reg = ModuleRegistry()
    mod_reg.add_hook("on_session_end", "x", lambda ctx: seen.append(ctx))

    provider = _StubProvider(responses=[_ok_response("ok")])
    agent = Agent(provider=provider, registry=Registry(), model="m")

    token = set_module_registry(mod_reg)
    try:
        agent.run("hi")
    finally:
        reset_module_registry(token)

    assert len(seen) == 1
    assert seen[0]["stopped_reason"] == "completed"
    assert seen[0]["iterations"] == 1


def test_on_session_end_fires_on_max_iterations() -> None:
    seen: list[dict[str, Any]] = []
    mod_reg = ModuleRegistry()
    mod_reg.add_hook("on_session_end", "x", lambda ctx: seen.append(ctx))

    # Provider always returns a tool call → loop exhausts max_iterations.
    provider = _StubProvider(responses=[_tool_call_response("echo", {"text": "x"})] * 5)
    agent = Agent(
        provider=provider, registry=_make_registry_with_echo(), model="m", max_iterations=3
    )

    token = set_module_registry(mod_reg)
    try:
        result = agent.run("loop")
    finally:
        reset_module_registry(token)

    assert result.stopped_reason == "max_iterations"
    assert len(seen) == 1
    assert seen[0]["stopped_reason"] == "max_iterations"
    assert seen[0]["iterations"] == 3
