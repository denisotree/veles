"""M78 — Ollama adapter (local-model provider via OpenAI-compatible endpoint)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from veles.adapters.local._base import _to_openai_message
from veles.adapters.local.ollama import OllamaProvider
from veles.core.provider import Message, ToolCall

# ---------- mock OpenAI client ----------


@dataclass
class _Choice:
    message: Any
    finish_reason: str | None = None


@dataclass
class _ChunkChoice:
    delta: Any
    finish_reason: str | None = None


@dataclass
class _Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class _Completion:
    choices: list[_Choice]
    usage: _Usage | None


@dataclass
class _Chunk:
    choices: list[_ChunkChoice]
    usage: _Usage | None = None


@dataclass
class _AssistantMessage:
    content: str | None = None
    tool_calls: list[Any] | None = None


@dataclass
class _Delta:
    content: str | None = None
    tool_calls: list[Any] | None = None


@dataclass
class _ToolFunction:
    name: str
    arguments: str


@dataclass
class _ToolCall:
    id: str
    function: _ToolFunction


class _SimpleNamespace:
    def __init__(self, **kw: Any) -> None:
        self.__dict__.update(kw)


class _StubChat:
    def __init__(self, results: list[Any]) -> None:
        self._results = list(results)
        self.last_kwargs: dict[str, Any] | None = None

    def create(self, **kwargs: Any) -> Any:
        self.last_kwargs = kwargs
        if not self._results:
            raise RuntimeError("no canned response prepared")
        return self._results.pop(0)


class _StubClient:
    def __init__(self, results: list[Any] | None = None) -> None:
        self.chat = _SimpleNamespace(completions=_StubChat(results or []))
        self.base_url = "http://localhost:11434/v1"


# ---------- defaults / construction ----------


def test_defaults_no_api_key_required() -> None:
    """Ollama never asks for a key — construction must not consult env."""
    p = OllamaProvider(client=_StubClient())
    assert p.name == "ollama"
    assert p.supports_streaming is True
    assert p.supports_tools is False  # off by default


def test_enable_tools_flag() -> None:
    p = OllamaProvider(client=_StubClient(), enable_tools=True)
    assert p.supports_tools is True


def test_base_url_env_overrides_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://gpu-box.lan:11434/v1")
    fake_openai = MagicMock(return_value=MagicMock())
    with patch("veles.adapters.local._base.OpenAI", fake_openai):
        OllamaProvider()
    kwargs = fake_openai.call_args.kwargs
    assert kwargs["base_url"] == "http://gpu-box.lan:11434/v1"
    assert kwargs["api_key"] == "local"  # placeholder, server ignores it


def test_default_base_url_when_no_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    fake_openai = MagicMock(return_value=MagicMock())
    with patch("veles.adapters.local._base.OpenAI", fake_openai):
        OllamaProvider()
    assert fake_openai.call_args.kwargs["base_url"] == "http://localhost:11434/v1"


def test_inactivity_timeout_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    """`inactivity_timeout` becomes the httpx Timeout `read` value (per-chunk gap)."""
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    fake_openai = MagicMock(return_value=MagicMock())
    captured: dict[str, Any] = {}

    def _fake_httpx_client(*, timeout: Any) -> MagicMock:
        captured["timeout"] = timeout
        return MagicMock()

    with (
        patch("veles.adapters.local._base.OpenAI", fake_openai),
        patch("veles.adapters.local._base.httpx.Client", _fake_httpx_client),
    ):
        OllamaProvider(inactivity_timeout=900.0, request_timeout=1800.0, connect_timeout=5.0)

    timeout = captured["timeout"]
    assert timeout.read == 900.0
    assert timeout.connect == 5.0
    # request_timeout is set on OpenAI client itself
    assert fake_openai.call_args.kwargs["timeout"] == 1800.0


# ---------- create_message ----------


def test_create_message_returns_text() -> None:
    completion = _Completion(
        choices=[
            _Choice(
                message=_AssistantMessage(content="привет"),
                finish_reason="stop",
            )
        ],
        usage=_Usage(prompt_tokens=5, completion_tokens=3, total_tokens=8),
    )
    client = _StubClient([completion])
    p = OllamaProvider(client=client)
    resp = p.create_message([Message(role="user", content="hi")], model="llama3.2")
    assert resp.text == "привет"
    assert resp.tool_calls == []
    assert resp.usage.total_tokens == 8
    assert resp.finish_reason == "stop"


def test_create_message_passes_model() -> None:
    completion = _Completion(
        choices=[_Choice(message=_AssistantMessage(content="ok"))], usage=None
    )
    client = _StubClient([completion])
    p = OllamaProvider(client=client)
    p.create_message([Message(role="user", content="hi")], model="qwen2.5:7b")
    assert client.chat.completions.last_kwargs["model"] == "qwen2.5:7b"


def test_tools_NOT_forwarded_when_supports_tools_false() -> None:
    """Default off ⇒ tools arg is silently dropped, agent loop won't deadlock
    waiting for tool calls a tool-blind model would never emit."""
    completion = _Completion(
        choices=[_Choice(message=_AssistantMessage(content="ok"))], usage=None
    )
    client = _StubClient([completion])
    p = OllamaProvider(client=client)  # supports_tools=False
    p.create_message(
        [Message(role="user", content="hi")],
        tools=[{"type": "function", "function": {"name": "echo", "parameters": {}}}],
        model="llama3.2",
    )
    assert "tools" not in client.chat.completions.last_kwargs


def test_tools_forwarded_when_enabled() -> None:
    completion = _Completion(
        choices=[_Choice(message=_AssistantMessage(content="ok"))], usage=None
    )
    client = _StubClient([completion])
    p = OllamaProvider(client=client, enable_tools=True)
    p.create_message(
        [Message(role="user", content="hi")],
        tools=[{"type": "function", "function": {"name": "echo", "parameters": {}}}],
        model="llama3.1",
    )
    kw = client.chat.completions.last_kwargs
    assert kw["tools"][0]["function"]["name"] == "echo"
    assert kw["tool_choice"] == "auto"


def test_create_message_parses_tool_calls() -> None:
    completion = _Completion(
        choices=[
            _Choice(
                message=_AssistantMessage(
                    content=None,
                    tool_calls=[
                        _ToolCall(
                            id="c1",
                            function=_ToolFunction(name="echo", arguments='{"text": "hi"}'),
                        )
                    ],
                ),
                finish_reason="tool_calls",
            )
        ],
        usage=None,
    )
    p = OllamaProvider(client=_StubClient([completion]), enable_tools=True)
    resp = p.create_message(
        [Message(role="user", content="x")],
        tools=[{"type": "function", "function": {"name": "echo", "parameters": {}}}],
        model="llama3.1",
    )
    assert resp.text is None
    assert resp.tool_calls[0].name == "echo"
    assert resp.tool_calls[0].arguments == {"text": "hi"}


def test_malformed_tool_args_kept_raw() -> None:
    completion = _Completion(
        choices=[
            _Choice(
                message=_AssistantMessage(
                    content=None,
                    tool_calls=[
                        _ToolCall(
                            id="c1", function=_ToolFunction(name="echo", arguments="{garbage")
                        )
                    ],
                ),
                finish_reason="tool_calls",
            )
        ],
        usage=None,
    )
    p = OllamaProvider(client=_StubClient([completion]), enable_tools=True)
    resp = p.create_message(
        [Message(role="user", content="x")],
        tools=[{"type": "function", "function": {"name": "echo", "parameters": {}}}],
        model="llama3.1",
    )
    assert resp.tool_calls[0].arguments == {"_raw": "{garbage"}


# ---------- stream_message ----------


def test_stream_emits_deltas_then_end() -> None:
    chunks = [
        _Chunk(choices=[_ChunkChoice(delta=_Delta(content="hel"))]),
        _Chunk(choices=[_ChunkChoice(delta=_Delta(content="lo"))]),
        _Chunk(
            choices=[_ChunkChoice(delta=_Delta(content=None), finish_reason="stop")],
            usage=_Usage(prompt_tokens=2, completion_tokens=2, total_tokens=4),
        ),
    ]
    client = _StubClient([iter(chunks)])
    p = OllamaProvider(client=client)
    events = list(p.stream_message([Message(role="user", content="hi")], model="llama3.2"))
    deltas = [e for e in events if hasattr(e, "text")]
    assert "".join(d.text for d in deltas) == "hello"
    last = events[-1]
    assert hasattr(last, "response")
    assert last.response.text == "hello"
    assert last.response.usage.total_tokens == 4
    assert last.response.finish_reason == "stop"


# ---------- list_models ----------


def test_list_models_parses_tags(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_resp = MagicMock()
    fake_resp.json.return_value = {
        "models": [{"name": "llama3.2:1b"}, {"name": "qwen2.5:7b"}]
    }
    fake_resp.raise_for_status = MagicMock()
    fake_get = MagicMock(return_value=fake_resp)
    p = OllamaProvider(client=_StubClient())
    with patch("veles.adapters.local.ollama.httpx.get", fake_get):
        models = p.list_models()
    assert models == ["llama3.2:1b", "qwen2.5:7b"]
    # /v1 suffix stripped before calling /api/tags
    assert fake_get.call_args.args[0] == "http://localhost:11434/api/tags"


# ---------- helpers ----------


def test_to_openai_message_assistant_with_tool_calls() -> None:
    out = _to_openai_message(
        Message(
            role="assistant",
            content=None,
            tool_calls=[ToolCall(id="x", name="echo", arguments={"text": "y"})],
        )
    )
    assert out["tool_calls"][0]["function"]["arguments"] == '{"text": "y"}'


def test_to_openai_message_tool_requires_id() -> None:
    with pytest.raises(ValueError, match="tool_call_id"):
        _to_openai_message(Message(role="tool", content="r"))
