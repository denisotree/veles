"""M325: streams ask for usage (`stream_options.include_usage`).

Without the option OpenAI, llama.cpp, ollama and vLLM send no `usage` in a stream,
so every streamed turn counted 0 tokens and `--max-tokens-total` limited nothing.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace as Ns
from typing import Any

import pytest
from openai import APIStatusError

from veles.adapters.local.llamacpp import LlamaCppProvider
from veles.core.agent import Agent
from veles.core.context import TokenBudget, reset_budget, set_budget
from veles.core.openai_wire import _reset_json_mode_for_tests, _reset_stream_usage_for_tests
from veles.core.provider import Message, StreamEnd
from veles.core.tools.registry import Registry, ToolEntry


def _chunk(content: str | None = None, finish: str | None = None, usage: Any = None) -> Ns:
    choices = (
        []
        if content is None and finish is None
        else [Ns(delta=Ns(content=content, tool_calls=None), finish_reason=finish)]
    )
    return Ns(choices=choices, usage=usage)


def _tool_chunk() -> Ns:
    call = Ns(index=0, id="c1", function=Ns(name="noop", arguments="{}"))
    return Ns(
        choices=[Ns(delta=Ns(content=None, tool_calls=[call]), finish_reason="tool_calls")],
        usage=None,
    )


_USAGE = Ns(prompt_tokens=45, completion_tokens=30, total_tokens=75)


def _bad_request(param: str) -> APIStatusError:
    return APIStatusError(
        f"400: unknown parameter '{param}'",
        response=Ns(status_code=400, headers={}, request=None),  # type: ignore[arg-type]
        body=None,
    )


class _StubChat:
    """Streams `script` (one list of chunks per call); can reject a parameter once."""

    def __init__(self, *scripts: list[Ns], reject: str | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._scripts = list(scripts)
        self._reject = reject

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self._reject and self._reject in kwargs:
            self._reject = None
            raise _bad_request("stream_options")
        return iter(self._scripts.pop(0))


def _provider(chat: _StubChat, *, tools: bool = False) -> LlamaCppProvider:
    client = Ns(chat=Ns(completions=chat), base_url="http://x/v1")
    return LlamaCppProvider(client=client, enable_tools=tools)  # type: ignore[arg-type]


def _stream(provider: LlamaCppProvider) -> Any:
    events = list(provider.stream_message([Message(role="user", content="hi")], model="m"))
    end = events[-1]
    assert isinstance(end, StreamEnd)
    return end.response


@pytest.fixture(autouse=True)
def _fresh_flags():
    _reset_stream_usage_for_tests()
    _reset_json_mode_for_tests()
    yield
    _reset_stream_usage_for_tests()
    _reset_json_mode_for_tests()


def test_stream_asks_for_usage_and_reads_it_from_the_last_chunk() -> None:
    chat = _StubChat([_chunk("hel"), _chunk("lo", finish="stop"), _chunk(usage=_USAGE)])
    response = _stream(_provider(chat))
    assert chat.calls[0]["stream_options"] == {"include_usage": True}
    assert response.text == "hello"
    assert response.usage.total_tokens == 75
    assert response.usage.completion_tokens == 30


def test_rejected_stream_options_self_heals_for_the_process() -> None:
    chat = _StubChat(
        [_chunk("a", finish="stop")],
        [_chunk("b", finish="stop")],
        reject="stream_options",
    )
    provider = _provider(chat)
    assert _stream(provider).text == "a"
    assert "stream_options" in chat.calls[0]
    assert "stream_options" not in chat.calls[1]  # the retry
    _stream(provider)
    assert "stream_options" not in chat.calls[2]  # and every later call


def test_missing_usage_warns_once(caplog: pytest.LogCaptureFixture) -> None:
    chat = _StubChat([_chunk("a", finish="stop")], [_chunk("b", finish="stop")])
    provider = _provider(chat)
    with caplog.at_level(logging.WARNING, logger="veles.core.openai_wire"):
        _stream(provider)
        _stream(provider)
    warnings = [r for r in caplog.records if "no token usage" in r.getMessage()]
    assert len(warnings) == 1


def test_unfinished_stream_does_not_warn(caplog: pytest.LogCaptureFixture) -> None:
    """A stream cut short (no `finish_reason`) is not evidence the backend ignores
    the option."""
    chat = _StubChat([_chunk("a")])
    with caplog.at_level(logging.WARNING, logger="veles.core.openai_wire"):
        _stream(_provider(chat))
    assert not [r for r in caplog.records if "no token usage" in r.getMessage()]


def test_streamed_usage_reaches_the_budget() -> None:
    """The reported failure end to end: a streamed tool round spends 75 tokens
    against a 50-token budget, so the next round stops on `budget_exhausted`."""
    chat = _StubChat([_tool_chunk(), _chunk(usage=_USAGE)])
    registry = Registry()
    registry.register(
        ToolEntry(
            name="noop",
            description="does nothing",
            parameter_schema={"type": "object", "properties": {}},
            handler=lambda: "ok",
            is_async=False,
        )
    )
    agent = Agent(
        provider=_provider(chat, tools=True), registry=registry, model="m", max_tokens=100
    )
    budget = TokenBudget(limit=50)
    token = set_budget(budget)
    try:
        result = agent.run("hi", on_text_delta=lambda _: None)
    finally:
        reset_budget(token)
    assert budget.consumed == 75
    assert result.stopped_reason == "budget_exhausted"
