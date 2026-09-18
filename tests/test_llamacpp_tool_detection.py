"""M256: llama.cpp tool-call support is auto-detected from `GET /props`.

Before this, only ollama could be probed (`/api/show` → `capabilities`), so
`_apply_local_tool_policy` set `supports_tools = False` for `llamacpp` and
`openai-compat` unconditionally and `VELES_LOCAL_TOOLS=1` was the only way in.
Since tools are how an agent reaches any data at all, a local run could not
produce a grounded answer in principle.

**The two backends answer different questions, which is why this is not a copy
of the ollama probe.** ollama holds many models and reports per-model
capabilities. A llama.cpp server holds exactly ONE model, given at startup, and
since b~10000 `--jinja` is on by default — so tool support is a property of the
loaded GGUF's chat template, which `/props` reports as `chat_template_caps`.

The payloads below are verbatim from llama.cpp **b10809** serving
**Qwen3.8-27B-UD-Q4_K_M**, captured 2026-09-18. The negative case is the same
model and server started with `--chat-template` pointing at a plain template that
has no tools support — so it proves the probe reads a real signal rather than
returning a constant, which is the failure a positive-only test would miss.
"""

from __future__ import annotations

import json

import httpx
import pytest

from veles.adapters.local.llamacpp import LlamaCppProvider
from veles.core.provider_factory import make_provider

# Verbatim from the live server with the model's own chat template.
CAPS_WITH_TOOLS = {
    "supports_object_arguments": True,
    "supports_parallel_tool_calls": True,
    "supports_preserve_reasoning": True,
    "supports_reasoning_effort": True,
    "supports_string_content": True,
    "supports_system_role": True,
    "supports_tool_calls": True,
    "supports_tools": True,
    "supports_typed_content": False,
}

# Same model, same build, started with a tools-less chat template.
CAPS_WITHOUT_TOOLS = {
    "supports_object_arguments": False,
    "supports_parallel_tool_calls": False,
    "supports_preserve_reasoning": False,
    "supports_reasoning_effort": False,
    "supports_string_content": True,
    "supports_system_role": True,
    "supports_tool_calls": False,
    "supports_tools": False,
    "supports_typed_content": False,
}


def _props(monkeypatch, payload, *, status: int = 200, seen: list[str] | None = None):
    def _get(url, **_kw):
        if seen is not None:
            seen.append(url)
        # `request=` is not optional here: `raise_for_status()` on a Response
        # with no request raises RuntimeError, which the probe's `except
        # Exception` would swallow into a False — passing the negative tests for
        # the wrong reason while the positive ones fail.
        return httpx.Response(
            status, content=json.dumps(payload), request=httpx.Request("GET", url)
        )

    monkeypatch.setattr("httpx.get", _get)


@pytest.fixture(autouse=True)
def _no_env_override(monkeypatch):
    monkeypatch.delenv("VELES_LOCAL_TOOLS", raising=False)


def test_detects_a_tool_capable_template(monkeypatch) -> None:
    _props(monkeypatch, {"chat_template_caps": CAPS_WITH_TOOLS})
    assert LlamaCppProvider().model_supports_tools("") is True


def test_detects_a_template_without_tools(monkeypatch) -> None:
    _props(monkeypatch, {"chat_template_caps": CAPS_WITHOUT_TOOLS})
    assert LlamaCppProvider().model_supports_tools("") is False


def test_both_halves_are_required(monkeypatch) -> None:
    """`supports_tools` means the template accepts tool definitions,
    `supports_tool_calls` that it renders the model's calls back out. An agent
    loop needs both, so a template offering only one is not usable."""
    half = {**CAPS_WITH_TOOLS, "supports_tool_calls": False}
    _props(monkeypatch, {"chat_template_caps": half})
    assert LlamaCppProvider().model_supports_tools("") is False


def test_props_is_queried_at_the_server_root(monkeypatch) -> None:
    """`/props` sits at the root while the OpenAI surface is under `/v1` — the
    same `/v1` strip ollama's probe does for `/api/show`."""
    seen: list[str] = []
    _props(monkeypatch, {"chat_template_caps": CAPS_WITH_TOOLS}, seen=seen)
    LlamaCppProvider().model_supports_tools("")
    assert seen == ["http://localhost:8080/props"]


def test_an_unreachable_server_is_not_tool_capable(monkeypatch) -> None:
    def _boom(url, **_kw):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr("httpx.get", _boom)
    assert LlamaCppProvider().model_supports_tools("") is False


def test_a_build_without_chat_template_caps_is_not_tool_capable(monkeypatch) -> None:
    """A build predating the field answers 200 without it — degrade to the
    pre-M256 behaviour rather than guess from the raw jinja string."""
    _props(monkeypatch, {"model_path": "/x.gguf"})
    assert LlamaCppProvider().model_supports_tools("") is False


def test_a_backend_with_no_props_endpoint_is_not_tool_capable(monkeypatch) -> None:
    """`openai-compat` pointed at something that isn't llama.cpp: 404, no tools,
    no crash."""
    _props(monkeypatch, {"error": "not found"}, status=404)
    assert LlamaCppProvider().model_supports_tools("") is False


def test_factory_turns_tools_on_without_a_model_name(monkeypatch) -> None:
    """The behaviour change: `make_provider("llamacpp")` carries no model name,
    because a llama.cpp server already knows which model it serves. The factory
    used to refuse to probe without one and left the provider tool-blind."""
    _props(monkeypatch, {"chat_template_caps": CAPS_WITH_TOOLS})
    assert make_provider("llamacpp").supports_tools is True


def test_env_override_still_wins(monkeypatch) -> None:
    _props(monkeypatch, {"chat_template_caps": CAPS_WITHOUT_TOOLS})
    monkeypatch.setenv("VELES_LOCAL_TOOLS", "1")
    assert make_provider("llamacpp").supports_tools is True
