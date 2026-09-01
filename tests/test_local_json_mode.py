"""M239: constrained JSON decoding for local backends.

Small open-weight models fail structured output far more often than they fail
the reasoning behind it — SKILL.state (arXiv 2608.26263) puts 20% of failures on
schema/type coercion and 12% on raw JSON syntax, "structured output adherence
rather than reasoning capacity". Veles' only defence was re-prompting
(`_PARSE_NUDGE_LIMIT`), which costs a round trip per attempt.

ollama and llama.cpp both honour OpenAI's `response_format`, and both constrain
decoding rather than merely asking. This is opt-in per call (`strict_json_mode`)
because the fenced-tools path needs prose around its ```veles-tool blocks, which
`json_object` would forbid.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from veles.adapters.local._base import _reset_json_mode_for_tests, json_mode_enabled
from veles.adapters.local.ollama import OllamaProvider
from veles.core.context import expects_strict_json, strict_json_mode
from veles.core.provider import Message


@dataclass
class _Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class _Msg:
    content: str | None = "{}"
    tool_calls: list[Any] | None = None


@dataclass
class _Choice:
    message: _Msg
    finish_reason: str | None = "stop"


@dataclass
class _Completion:
    choices: list[_Choice]
    usage: _Usage | None = None


class _Namespace:
    def __init__(self, **kw: Any) -> None:
        self.__dict__.update(kw)


class _StubChat:
    """Records kwargs; can be told to reject `response_format` once."""

    def __init__(self, *, reject_response_format: bool = False) -> None:
        self.calls: list[dict[str, Any]] = []
        self._reject = reject_response_format

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self._reject and "response_format" in kwargs:
            from openai import APIStatusError

            raise APIStatusError(
                "400: unknown parameter 'response_format'",
                response=_Namespace(status_code=400, headers={}, request=None),  # type: ignore[arg-type]
                body=None,
            )
        return _Completion(choices=[_Choice(message=_Msg())], usage=_Usage())


def _provider(chat: _StubChat) -> OllamaProvider:
    client = _Namespace(chat=_Namespace(completions=chat), base_url="http://x/v1")
    return OllamaProvider(client=client)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def _fresh_json_mode():
    _reset_json_mode_for_tests()
    yield
    _reset_json_mode_for_tests()


# ---------- the flag itself ----------


def test_strict_json_is_off_by_default() -> None:
    assert expects_strict_json() is False


def test_strict_json_mode_scopes_and_restores() -> None:
    with strict_json_mode():
        assert expects_strict_json() is True
    assert expects_strict_json() is False


# ---------- wire behaviour ----------


def test_no_response_format_outside_strict_mode() -> None:
    """The default agentic turn must stay untouched — `json_object` would
    forbid the prose the fenced-tools path needs around its blocks."""
    chat = _StubChat()
    _provider(chat).create_message([Message(role="user", content="hi")], model="llama3")
    assert "response_format" not in chat.calls[0]


def test_response_format_sent_inside_strict_mode() -> None:
    chat = _StubChat()
    with strict_json_mode():
        _provider(chat).create_message([Message(role="user", content="hi")], model="llama3")
    assert chat.calls[0]["response_format"] == {"type": "json_object"}


def test_env_switch_disables_json_mode(monkeypatch) -> None:
    monkeypatch.setenv("VELES_LOCAL_JSON_MODE", "0")
    import importlib

    from veles.adapters.local import _base

    importlib.reload(_base)
    try:
        assert _base.json_mode_enabled() is False
    finally:
        monkeypatch.delenv("VELES_LOCAL_JSON_MODE", raising=False)
        importlib.reload(_base)


# ---------- self-heal ----------


def test_rejected_response_format_self_heals_and_retries() -> None:
    """A backend that doesn't know the parameter must degrade, not fail the
    turn — same contract as M220's cache_control tool-tail self-heal."""
    chat = _StubChat(reject_response_format=True)
    with strict_json_mode():
        resp = _provider(chat).create_message([Message(role="user", content="hi")], model="llama3")

    assert resp.text == "{}", "the retry succeeded"
    assert len(chat.calls) == 2, "one rejected call, one retry"
    assert "response_format" in chat.calls[0]
    assert "response_format" not in chat.calls[1]
    assert json_mode_enabled() is False, "disabled process-wide after the rejection"


def test_self_heal_stops_sending_it_on_later_calls() -> None:
    chat = _StubChat(reject_response_format=True)
    provider = _provider(chat)
    with strict_json_mode():
        provider.create_message([Message(role="user", content="a")], model="llama3")
        provider.create_message([Message(role="user", content="b")], model="llama3")

    # call 0 rejected, call 1 retry, call 2 never carries the parameter again.
    assert len(chat.calls) == 3
    assert "response_format" not in chat.calls[2]
