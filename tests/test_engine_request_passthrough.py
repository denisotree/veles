"""M250: `[engine.request.<provider>]` is forwarded into the request body verbatim,
and the response's real backend / reasoning split comes back in the trace.

Two invariants carry the milestone:

1. The passthrough and OpenRouter's M224 sticky-routing `session_id` travel in
   the SAME `extra_body` object. Before M250 the OpenRouter override *replaced*
   whatever the base returned, so a naive merge would silently drop the pin (or
   the session id) — hence the explicit both-present assertions below.
2. The section is keyed by `Provider.name`. One project config outlives a
   backend switch, and an OpenRouter `provider` block sent to llama.cpp is a
   400 — so a section written for one backend must be invisible to the other.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from veles.core.context import (
    reset_active_project,
    reset_current_session_id,
    set_active_project,
    set_current_session_id,
)
from veles.core.openai_wire import request_body_overrides, upstream_provider_of
from veles.core.project import init_project
from veles.core.project_config import save_project_config
from veles.core.provider import Message

PIN = {
    "provider": {"quantizations": ["bf16"], "order": ["AkashML"], "allow_fallbacks": False},
    "reasoning": {"enabled": False},
}


@pytest.fixture(autouse=True)
def _clear_session():
    tok = set_current_session_id(None)
    yield
    reset_current_session_id(tok)


@pytest.fixture()
def project_with(tmp_path, monkeypatch):
    """Activate a project whose config declares `[engine.request.<section>]`."""
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    tokens: list = []

    def _make(section: str | None, body: dict | None = None):
        project = init_project(tmp_path / "proj", name="proj")
        if section is not None:
            save_project_config(project, {"engine": {"request": {section: body or PIN}}})
        tokens.append(set_active_project(project))
        return project

    yield _make
    for tok in reversed(tokens):
        reset_active_project(tok)


def _openrouter():
    from veles.adapters.openrouter import OpenRouterProvider

    return OpenRouterProvider(api_key="sk-test")  # offline: no network at construction


# ---- reading the section ----


def test_no_active_project_means_no_overrides() -> None:
    assert request_body_overrides("openrouter") == {}


def test_section_is_read_for_the_matching_provider(project_with) -> None:
    project_with("openrouter")
    assert request_body_overrides("openrouter") == PIN


def test_section_is_invisible_to_another_provider(project_with) -> None:
    """The reason the section is provider-keyed: the paused llama.cpp migration
    reuses this same config file, and OpenRouter's `provider` block is a 400
    there."""
    project_with("openrouter")
    assert request_body_overrides("llamacpp") == {}


def test_unknown_provider_section_raises(project_with) -> None:
    """M255: config is written by hand, so it is sometimes wrong. Every other
    mistake here fails loudly at the upstream — a misspelt provider was the one
    that didn't, silently running the measurement unpinned."""
    from veles.core.config_schema import ConfigError

    project_with("openrotuer")
    with pytest.raises(ConfigError) as exc:
        request_body_overrides("openrouter")
    message = str(exc.value)
    assert "openrotuer" in message
    assert "config.toml" in message  # points at the file to edit
    assert "openrouter" in message  # and lists what was meant


def test_unknown_provider_section_raises_through_the_request_path(project_with) -> None:
    """Not just the reader: the error reaches the caller through the same hook
    that builds the request, so a bad pin cannot start a run."""
    from veles.core.config_schema import ConfigError

    project_with("openrotuer")
    with pytest.raises(ConfigError):
        _openrouter()._request_options("z-ai/glm-5.3-flash")


def test_known_provider_other_than_the_active_one_is_not_an_error(project_with) -> None:
    """The counterpart guard: keeping llama.cpp's knobs next to OpenRouter's in
    one file is the POINT of provider-scoping, not a mistake."""
    project_with("llamacpp")
    assert request_body_overrides("openrouter") == {}


def test_path_typo_raises_too(tmp_path, monkeypatch) -> None:
    """`[engine.reqest.…]` leaves `[engine.request]` absent, which is also the
    normal state of a project with no pin — so it is only visible one level up,
    as an unknown key under `[engine]`. It raises all the same: a pin that never
    reaches the wire is exactly the silent fallback M255 exists to remove."""
    from veles.core.config_schema import ConfigError

    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    project = init_project(tmp_path / "proj", name="proj")
    (project.state_dir / "config.toml").write_text(
        '[engine]\nprovider = "openrouter"\n\n'
        "[engine.reqest.openrouter.provider]\n"
        'order = ["GMICloud"]\n',
        encoding="utf-8",
    )
    tok = set_active_project(project)
    try:
        with pytest.raises(ConfigError) as exc:
            request_body_overrides("openrouter")
    finally:
        reset_active_project(tok)
    assert "reqest" in str(exc.value)


def test_validator_reports_both_typo_shapes(tmp_path, monkeypatch) -> None:
    """`veles doctor` / `daemon start` see both shapes without running a turn —
    the same findings the reader raises on, for providers that never call it."""
    from veles.core.config_schema import validate_config

    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    project = init_project(tmp_path / "proj", name="proj")
    (project.state_dir / "config.toml").write_text(
        '[engine]\nprovider = "openrouter"\n\n'
        "[engine.request.openrotuer.provider]\n"
        'order = ["GMICloud"]\n\n'
        "[engine.reqest.openrouter.provider]\n"
        'order = ["GMICloud"]\n',
        encoding="utf-8",
    )
    from veles.core.project_config import load_project_config

    found = {(f.section, f.key) for f in validate_config(load_project_config(project))}
    assert ("engine.request", "openrotuer") in found
    assert ("engine", "reqest") in found


def test_validator_accepts_a_correct_engine_section(tmp_path, monkeypatch) -> None:
    """The failure mode worse than a silent fallback is erroring on a config
    that works — `provider`/`model`/`request` must all pass."""
    from veles.core.config_schema import validate_config
    from veles.core.project_config import load_project_config

    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    project = init_project(tmp_path / "proj", name="proj")
    (project.state_dir / "config.toml").write_text(
        '[engine]\nprovider = "openrouter"\nmodel = "z-ai/glm-5.3-flash"\n\n'
        "[engine.request.openrouter.provider]\n"
        'order = ["GMICloud"]\n',
        encoding="utf-8",
    )
    assert validate_config(load_project_config(project)) == []


def test_hand_written_toml_round_trips(tmp_path, monkeypatch) -> None:
    """The shape a user actually types, parsed by tomllib — not a dict handed to
    `save_project_config`. The section is four levels deep and carries a bool
    (`allow_fallbacks = false`) in the innermost table, which is exactly where a
    round-trip would quietly drop something."""
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    project = init_project(tmp_path / "proj", name="proj")
    (project.state_dir / "config.toml").write_text(
        "[engine]\n"
        'provider = "openrouter"\n'
        'model = "z-ai/glm-5.3-flash"\n'
        "\n"
        "[engine.request.openrouter.provider]\n"
        'order = ["GMICloud"]\n'
        "allow_fallbacks = false\n"
        "\n"
        "[engine.request.openrouter.reasoning]\n"
        "enabled = false\n",
        encoding="utf-8",
    )
    tok = set_active_project(project)
    try:
        assert request_body_overrides("openrouter") == {
            "provider": {"order": ["GMICloud"], "allow_fallbacks": False},
            "reasoning": {"enabled": False},
        }
        assert request_body_overrides("llamacpp") == {}
    finally:
        reset_active_project(tok)


def test_absent_section_changes_nothing(project_with) -> None:
    project_with(None)
    assert request_body_overrides("openrouter") == {}
    assert _openrouter()._request_options("z-ai/glm-5.3-flash") == {}


# ---- merging with sticky routing ----


def test_pin_and_session_id_share_one_extra_body(project_with) -> None:
    project_with("openrouter")
    tok = set_current_session_id("sess-abc")
    try:
        opts = _openrouter()._request_options("z-ai/glm-5.3-flash")
    finally:
        reset_current_session_id(tok)
    assert opts["extra_body"] == {**PIN, "session_id": "sess-abc"}


def test_pin_survives_without_a_session(project_with) -> None:
    project_with("openrouter")
    assert _openrouter()._request_options("z-ai/glm-5.3-flash") == {"extra_body": PIN}


def test_explicit_session_id_in_config_wins(project_with) -> None:
    """The section is a verbatim passthrough — an explicitly configured key is
    the user's intent and beats the runtime default."""
    project_with("openrouter", {"session_id": "pinned-by-hand"})
    tok = set_current_session_id("sess-abc")
    try:
        opts = _openrouter()._request_options("z-ai/glm-5.3-flash")
    finally:
        reset_current_session_id(tok)
    assert opts["extra_body"]["session_id"] == "pinned-by-hand"


def test_local_json_mode_and_pin_coexist(project_with) -> None:
    """`response_format` is a top-level key, the pin lives in `extra_body` —
    the local adapter's M239 override must keep both."""
    from veles.adapters.local.llamacpp import LlamaCppProvider
    from veles.core.context import strict_json_mode

    project_with("llamacpp", {"cache_prompt": True})
    provider = LlamaCppProvider(client=SimpleNamespace())
    with strict_json_mode():
        opts = provider._request_options("qwen3.8-27b")
    assert opts["extra_body"] == {"cache_prompt": True}
    assert opts["response_format"] == {"type": "json_object"}


def test_create_message_puts_the_pin_on_the_wire(project_with) -> None:
    project_with("openrouter")
    captured: dict = {}

    class _FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="ok", tool_calls=[]),
                        finish_reason="stop",
                    )
                ],
                usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
                provider="AkashML",
            )

    provider = _openrouter()
    provider._client = SimpleNamespace(chat=SimpleNamespace(completions=_FakeCompletions()))
    response = provider.create_message([Message(role="user", content="hi")], model="m")
    assert captured["extra_body"] == PIN
    assert response.upstream_provider == "AkashML"


# ---- reading the response back ----


def test_upstream_provider_from_a_plain_attribute() -> None:
    assert upstream_provider_of(SimpleNamespace(provider="Relace")) == "Relace"


def test_upstream_provider_from_model_extra() -> None:
    """Pydantic keeps unknown fields in `model_extra`; don't rely on attribute
    access alone."""
    obj = SimpleNamespace(model_extra={"provider": "AkashML"})
    assert upstream_provider_of(obj) == "AkashML"


def test_upstream_provider_absent_is_none() -> None:
    assert upstream_provider_of(SimpleNamespace()) is None


def test_stream_captures_provider_and_reasoning_tokens() -> None:
    """Verified live against OpenRouter: `provider` rides on every chunk, and
    `usage.completion_tokens_details.reasoning_tokens` reports the thinking
    split. Both reach `StreamEnd`."""
    from veles.core.provider import StreamEnd

    def _chunk(*, content=None, usage=None, finish=None):
        delta = SimpleNamespace(content=content, tool_calls=[], reasoning=None)
        return SimpleNamespace(
            provider="Relace",
            usage=usage,
            choices=[SimpleNamespace(delta=delta, finish_reason=finish)],
        )

    usage = SimpleNamespace(
        prompt_tokens=13,
        completion_tokens=100,
        total_tokens=113,
        cost=0.00000147,
        completion_tokens_details=SimpleNamespace(reasoning_tokens=97),
        prompt_tokens_details=SimpleNamespace(cached_tokens=0),
    )

    class _FakeCompletions:
        def create(self, **kwargs):
            return iter(
                [_chunk(content="hi"), _chunk(finish="length", usage=usage)],
            )

    provider = _openrouter()
    provider._client = SimpleNamespace(chat=SimpleNamespace(completions=_FakeCompletions()))
    events = list(provider.stream_message([Message(role="user", content="q")], model="m"))
    end = next(e for e in events if isinstance(e, StreamEnd))
    assert end.response.upstream_provider == "Relace"
    assert end.response.finish_reason == "length"
    assert end.response.usage.reasoning_tokens == 97
    assert end.response.usage.cost_usd == pytest.approx(0.00000147)


def test_trace_records_intent_and_fact(tmp_path, project_with) -> None:
    """The trace carries both what we asked for (`request_extra`) and what
    answered (`upstream_provider`) — a pin that silently did nothing shows up as
    a mismatch instead of as unexplained variance."""
    import json

    from veles.core.agent import Agent
    from veles.core.provider import ProviderResponse, TokenUsage
    from veles.core.tools.registry import Registry
    from veles.core.trace import TraceWriter

    project_with("openrouter")

    class _Provider:
        name = "openrouter"
        supports_tools = False
        supports_streaming = False

        def create_message(self, messages, tools=None, *, model, max_tokens=4096):
            return ProviderResponse(
                text="done",
                tool_calls=[],
                usage=TokenUsage(completion_tokens=100, reasoning_tokens=97, cost_usd=0.0002),
                finish_reason="stop",
                upstream_provider="AkashML",
            )

    trace_path = tmp_path / "traces.jsonl"
    agent = Agent(
        provider=_Provider(),
        registry=Registry(),
        model="z-ai/glm-5.3-flash",
        trace_writer=TraceWriter(trace_path),
    )
    agent.run("hello")

    record = json.loads(trace_path.read_text().splitlines()[0])
    assert record["upstream_provider"] == "AkashML"
    assert record["request_extra"] == PIN
    assert record["reasoning_tokens"] == 97
    assert record["est_cost_usd"] == pytest.approx(0.0002)
