"""M325: one place decides the completion cap, and a local server's word beats the name.

The reported failures: `--model bonsai-2-27b` against a llama.cpp server running a
reasoning model got 4096 while `--model qwen3.8-27b` against the same server got
32000 — llama.cpp ignores the name, so the cap depended on a string the user made
up; nothing could override it (`--max-tokens` silently meant `--max-tokens-total`);
and the daemon and `veles job` passed a hard 4096 that bypassed M247 for every model.
"""

from __future__ import annotations

import argparse
import json

import httpx
import pytest

from veles.adapters.local.llamacpp import LlamaCppProvider
from veles.core.agent import Agent, run_oneshot
from veles.core.config_schema import ConfigError
from veles.core.context import reset_active_project, set_active_project
from veles.core.model_budgets import resolve_max_tokens, side_call_max_tokens
from veles.core.project import init_project
from veles.core.project_config import save_project_config
from veles.core.provider import ProviderResponse, ServerFacts, TokenUsage
from veles.core.tools.registry import Registry

REASONING = ServerFacts(tools=True, reasoning=True, n_ctx=65536)
PLAIN = ServerFacts(tools=True, reasoning=False, n_ctx=65536)


@pytest.fixture()
def engine(tmp_path, monkeypatch):
    """Activate a project whose config declares `[engine]`."""
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    tokens: list = []

    def _make(section: dict):
        project = init_project(tmp_path / "proj", name="proj")
        save_project_config(project, {"engine": section})
        tokens.append(set_active_project(project))
        return project

    yield _make
    for tok in reversed(tokens):
        reset_active_project(tok)


# ---- resolve_max_tokens ----


def test_a_reasoning_server_beats_a_made_up_name() -> None:
    assert resolve_max_tokens("bonsai-2-27b", REASONING) == (32000, "server: reasoning template")


def test_without_facts_the_name_still_decides() -> None:
    assert resolve_max_tokens("bonsai-2-27b") == (4096, "model id")
    assert resolve_max_tokens("qwen3.8-27b") == (32000, "model id: reasoning")


def test_a_plain_template_does_not_lower_a_reasoning_name() -> None:
    """The facts only raise the cap: under-capping truncates, over-capping is free."""
    assert resolve_max_tokens("qwen3.8-27b", PLAIN)[0] == 32000


def test_engine_max_tokens_beats_the_server(engine) -> None:
    engine({"max_tokens": 8000})
    assert resolve_max_tokens("bonsai-2-27b", REASONING) == (8000, "[engine] max_tokens")


def test_explicit_beats_engine(engine) -> None:
    engine({"max_tokens": 8000})
    assert resolve_max_tokens("m", REASONING, explicit=1000) == (1000, "explicit")


@pytest.mark.parametrize("bad", ["many", 0, -1, 1.5, True])
def test_a_nonsense_engine_cap_is_an_error(engine, bad) -> None:
    engine({"max_tokens": bad})
    with pytest.raises(ConfigError):
        resolve_max_tokens("m")


def test_never_above_the_servers_context() -> None:
    small = ServerFacts(reasoning=True, n_ctx=16384)
    value, source = resolve_max_tokens("m", small)
    assert value == 16384
    assert "n_ctx" in source


# ---- side calls ----


def test_a_side_call_keeps_its_answer_size_on_a_quiet_model() -> None:
    assert side_call_max_tokens("bonsai-2-27b", PLAIN, 512) == 512


def test_a_side_call_gets_room_to_think_on_a_reasoning_model() -> None:
    """Found in M325: the summariser asked for 1024 and the auto-mode classifier
    for 8 — on a model that thinks first, that is an empty answer."""
    assert side_call_max_tokens("bonsai-2-27b", REASONING, 8) == 32000
    assert side_call_max_tokens("z-ai/glm-5.3-flash", None, 1024) == 32000


class _Recorder:
    name = "rec"
    supports_streaming = False
    supports_tools = False

    def __init__(self, facts: ServerFacts | None = None) -> None:
        self.facts = facts
        self.max_tokens: list[int] = []

    def create_message(self, messages, tools=None, *, model, max_tokens=4096):
        self.max_tokens.append(max_tokens)
        return ProviderResponse(text="ok", tool_calls=[], usage=TokenUsage(), finish_reason="stop")

    def stream_message(self, *a, **kw):  # pragma: no cover - not streamed here
        raise NotImplementedError


def test_run_oneshot_widens_a_small_cap_for_a_thinker() -> None:
    provider = _Recorder(REASONING)
    run_oneshot(provider, "anything", "sys", "text", max_tokens=1024)
    assert provider.max_tokens == [32000]


def test_run_oneshot_keeps_a_small_cap_for_a_quiet_model() -> None:
    provider = _Recorder(PLAIN)
    run_oneshot(provider, "anything", "sys", "text", max_tokens=1024)
    assert provider.max_tokens == [1024]


# ---- the Agent ----


def test_agent_reads_the_providers_facts() -> None:
    provider = _Recorder(REASONING)
    Agent(provider=provider, registry=Registry(), model="anything").run("hi")
    assert provider.max_tokens == [32000]


def test_agent_ceiling_follows_the_servers_context() -> None:
    agent = Agent(provider=_Recorder(REASONING), registry=Registry(), model="anything")
    assert agent._hard_ceiling_tokens == int(65536 * 0.9)


def test_a_smaller_given_ceiling_is_kept() -> None:
    agent = Agent(
        provider=_Recorder(REASONING),
        registry=Registry(),
        model="anything",
        hard_ceiling_tokens=10_000,
    )
    assert agent._hard_ceiling_tokens == 10_000


def test_verbose_names_the_cap_and_its_source(capsys) -> None:
    Agent(provider=_Recorder(REASONING), registry=Registry(), model="m", verbose=True)
    assert "max_tokens=32000 (server: reasoning template)" in capsys.readouterr().err


def test_daemon_settings_leave_the_cap_to_the_agent(tmp_path) -> None:
    """The regression: `getattr(args, "max_tokens", 4096)` held every daemon and
    `veles job` agent to 4096 — glm-5.3-flash, M247's own example, included."""
    from veles.daemon.agent_factory import factory_settings_from_args

    project = init_project(tmp_path, name=None, force=False)
    settings = factory_settings_from_args(argparse.Namespace(model="z-ai/glm-5.3-flash"), project)
    assert settings.max_tokens is None
    agent = Agent(
        provider=_Recorder(),
        registry=Registry(),
        model=settings.model,
        max_tokens=settings.max_tokens,
    )
    assert agent._max_tokens == 32000


def test_the_commands_cap_reaches_what_args_cannot(engine) -> None:
    """`--max-tokens` is set for the whole command: a skill's sub-agent (built
    with no number) gets it, and a side call on a thinker is widened only up to
    it — not to 32000 past what the user set."""
    from veles.core.context import reset_run_max_tokens, set_run_max_tokens

    engine({"max_tokens": 20000})
    token = set_run_max_tokens(8000)
    try:
        assert resolve_max_tokens("bonsai-2-27b", REASONING) == (8000, "--max-tokens")
        assert side_call_max_tokens("bonsai-2-27b", REASONING, 1024) == 8000
        assert resolve_max_tokens("m", None, explicit=500)[0] == 500  # a caller's number wins
    finally:
        reset_run_max_tokens(token)


# ---- the CLI flag ----


def test_max_tokens_is_its_own_flag() -> None:
    """argparse's prefix matching used to read `--max-tokens 5000` as
    `--max-tokens-total 5000` — the advice in the truncation message raised the
    wrong limit."""
    from veles.cli._parsers import build_parser

    args = build_parser().parse_args(["run", "--max-tokens", "5000", "hi"])
    assert args.max_tokens == 5000
    assert args.max_tokens_total != 5000


def test_max_tokens_defaults_to_unset() -> None:
    from veles.cli._parsers import build_parser

    assert build_parser().parse_args(["run", "hi"]).max_tokens is None


# ---- the probe ----


def _props(monkeypatch, payload: dict) -> None:
    def _get(url, **_kw):
        return httpx.Response(200, content=json.dumps(payload), request=httpx.Request("GET", url))

    monkeypatch.setattr("httpx.get", _get)


@pytest.mark.parametrize(
    ("caps", "expected"),
    [
        ({"supports_reasoning_effort": True, "supports_preserve_reasoning": False}, True),
        ({"supports_reasoning_effort": False, "supports_preserve_reasoning": True}, True),
        ({"supports_reasoning_effort": False, "supports_preserve_reasoning": False}, False),
        ({"supports_tools": True}, None),
    ],
)
def test_props_reasoning_takes_either_flag(monkeypatch, caps, expected) -> None:
    _props(monkeypatch, {"chat_template_caps": caps})
    facts = LlamaCppProvider().server_facts("")
    assert facts is not None
    assert facts.reasoning is expected


# Live, llama.cpp b11146 serving Qwen3-0.6B-Q4_0 (2026-10-09): both flags false,
# yet it thinks by default — asked to "say pong" in 300 tokens it spent all 300
# on reasoning and returned empty content. The template is what gives it away.
_QWEN3_CAPS = {
    "supports_object_arguments": True,
    "supports_parallel_tool_calls": True,
    "supports_preserve_reasoning": False,
    "supports_reasoning_effort": False,
    "supports_string_content": True,
    "supports_system_role": True,
    "supports_tool_calls": True,
    "supports_tools": True,
    "supports_typed_content": False,
}


def test_a_thinking_template_counts_when_the_flags_say_no(monkeypatch) -> None:
    template = "{%- if enable_thinking is defined %}…<think>\n\n</think>…{%- endif %}"
    _props(monkeypatch, {"chat_template_caps": _QWEN3_CAPS, "chat_template": template})
    facts = LlamaCppProvider().server_facts("")
    assert facts is not None
    assert facts.reasoning is True


def test_a_plain_template_with_false_flags_is_not_reasoning(monkeypatch) -> None:
    _props(monkeypatch, {"chat_template_caps": _QWEN3_CAPS, "chat_template": "{{ messages }}"})
    facts = LlamaCppProvider().server_facts("")
    assert facts is not None
    assert facts.reasoning is False


def test_props_n_ctx(monkeypatch) -> None:
    _props(monkeypatch, {"chat_template_caps": {}, "default_generation_settings": {"n_ctx": 65536}})
    facts = LlamaCppProvider().server_facts("")
    assert facts is not None
    assert facts.n_ctx == 65536


def test_factory_keeps_the_facts_on_the_provider(monkeypatch) -> None:
    """One probe at construction serves the tools, the cap and the ceiling — also
    when `VELES_LOCAL_TOOLS` forces the tools decision."""
    from veles.core.provider_factory import make_provider

    monkeypatch.setenv("VELES_LOCAL_TOOLS", "0")
    _props(monkeypatch, {"chat_template_caps": {"supports_reasoning_effort": True}})
    provider = make_provider("llamacpp", model="bonsai-2-27b")
    assert provider.supports_tools is False
    assert provider.facts == ServerFacts(tools=False, reasoning=True, n_ctx=None)
