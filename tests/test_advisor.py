"""M44 — advisor pattern: parse / render / sub-agent integration."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import StubProvider
from veles.core.context import (
    reset_active_project,
    set_active_project,
)
from veles.core.project import init_project
from veles.core.provider import ProviderResponse, TokenUsage
from veles.core.tools.builtin.advisor import (
    Verdict,
    advisor_review,
    parse_verdict,
    render_verdict,
)

# ---------- parse_verdict ----------


def test_parse_verdict_strict_json() -> None:
    raw = '{"ok": true, "concerns": [], "suggestions": ["use a feature flag"]}'
    v = parse_verdict(raw)
    assert v.ok is True
    assert v.concerns == []
    assert v.suggestions == ["use a feature flag"]


def test_parse_verdict_with_concerns_sets_ok_false() -> None:
    raw = '{"ok": false, "concerns": ["missing tests"], "suggestions": []}'
    v = parse_verdict(raw)
    assert v.ok is False
    assert v.concerns == ["missing tests"]


def test_parse_verdict_strips_code_fences() -> None:
    raw = '```json\n{"ok": true, "concerns": [], "suggestions": []}\n```'
    v = parse_verdict(raw)
    assert v.ok is True


def test_parse_verdict_strips_unspecified_code_fences() -> None:
    raw = '```\n{"ok": true, "concerns": [], "suggestions": []}\n```'
    v = parse_verdict(raw)
    assert v.ok is True


def test_parse_verdict_invalid_json_returns_concerns() -> None:
    v = parse_verdict("not json at all")
    assert v.ok is False
    assert any("non-JSON" in c for c in v.concerns)


def test_parse_verdict_non_object_json_returns_concerns() -> None:
    v = parse_verdict("[1, 2, 3]")
    assert v.ok is False
    assert any("non-object" in c for c in v.concerns)


def test_parse_verdict_empty_input_returns_concerns() -> None:
    v = parse_verdict("")
    assert v.ok is False
    assert any("empty" in c for c in v.concerns)


def test_parse_verdict_filters_non_string_items() -> None:
    raw = '{"ok": true, "concerns": [42, "real", null], "suggestions": ["", "ok"]}'
    v = parse_verdict(raw)
    assert v.concerns == ["real"]
    assert v.suggestions == ["ok"]


def test_parse_verdict_missing_keys_defaults() -> None:
    v = parse_verdict('{"ok": true}')
    assert v.ok is True
    assert v.concerns == []
    assert v.suggestions == []


def test_parse_verdict_truncates_long_non_json_in_concern() -> None:
    big = "x" * 500
    v = parse_verdict(big)
    assert v.ok is False
    assert all(len(c) <= 250 for c in v.concerns)


# ---------- render_verdict ----------


def test_render_verdict_ok_no_items() -> None:
    rendered = render_verdict(Verdict(ok=True))
    assert rendered.startswith("ADVISOR VERDICT: OK")
    assert "(no concerns, no suggestions)" in rendered


def test_render_verdict_concerns_force_concerns_label() -> None:
    """ok=true but concerns present → label = CONCERNS (defensive)."""
    rendered = render_verdict(Verdict(ok=True, concerns=["x"]))
    assert "ADVISOR VERDICT: CONCERNS" in rendered


def test_render_verdict_concerns_label_and_bullets() -> None:
    rendered = render_verdict(Verdict(ok=False, concerns=["a", "b"], suggestions=["c"]))
    assert "ADVISOR VERDICT: CONCERNS" in rendered
    assert "Concerns:" in rendered
    assert "- a" in rendered
    assert "- b" in rendered
    assert "Suggestions:" in rendered
    assert "- c" in rendered


def test_render_verdict_only_suggestions() -> None:
    rendered = render_verdict(Verdict(ok=True, suggestions=["consider caching"]))
    assert "ADVISOR VERDICT: OK" in rendered
    assert "Suggestions:" in rendered
    assert "- consider caching" in rendered


# ---------- advisor_review (integration via stub provider) ----------


def _StubProvider(
    response_text: str = '{"ok": true, "concerns": [], "suggestions": []}',
) -> StubProvider:
    return StubProvider(
        [
            ProviderResponse(
                text=response_text,
                tool_calls=[],
                usage=TokenUsage(
                    prompt_tokens=10, completion_tokens=5, total_tokens=15
                ),
                finish_reason="stop",
            )
        ],
        supports_streaming=True,
        repeat_last=True,
    )


@pytest.fixture(autouse=True)
def _isolate_user_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    isolated = tmp_path / "_user_home"
    isolated.mkdir()
    monkeypatch.setenv("VELES_USER_HOME", str(isolated))
    monkeypatch.delenv("VELES_TRUST_AUTO_ALLOW", raising=False)
    token = set_active_project(None)
    yield
    reset_active_project(token)


def test_advisor_review_returns_unavailable_without_active_project() -> None:
    out = advisor_review("any plan")
    assert "<advisor unavailable" in out
    assert "no active project" in out


def test_advisor_review_returns_unavailable_when_no_api_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = init_project(tmp_path / "p", name="p")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    token = set_active_project(project)
    try:
        out = advisor_review("plan")
    finally:
        reset_active_project(token)
    assert "<advisor unavailable" in out
    assert "API key" in out


def test_advisor_review_renders_stub_verdict(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """End-to-end: stub the routed provider's make_provider, return canned JSON."""
    project = init_project(tmp_path / "p", name="p")
    monkeypatch.setenv("OPENROUTER_API_KEY", "stub")
    stub = _StubProvider(
        '{"ok": false, "concerns": ["scope unclear"], "suggestions": []}'
    )
    monkeypatch.setattr("veles.core.provider_factory.make_provider", lambda name: stub)
    token = set_active_project(project)
    try:
        out = advisor_review("ship the new auth flow on Monday")
    finally:
        reset_active_project(token)
    assert "ADVISOR VERDICT: CONCERNS" in out
    assert "- scope unclear" in out
    # The plan text reaches the sub-agent's first user message.
    last = stub.calls[-1]["messages"]
    assert any("ship the new auth flow" in (m.content or "") for m in last)


def test_advisor_review_handles_provider_construction_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = init_project(tmp_path / "p", name="p")
    monkeypatch.setenv("OPENROUTER_API_KEY", "stub")

    def boom(name: str):
        raise RuntimeError("kaboom")

    monkeypatch.setattr("veles.core.provider_factory.make_provider", boom)
    token = set_active_project(project)
    try:
        out = advisor_review("plan")
    finally:
        reset_active_project(token)
    assert "<advisor unavailable" in out
    assert "kaboom" in out


def test_advisor_review_handles_subagent_exception(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = init_project(tmp_path / "p", name="p")
    monkeypatch.setenv("OPENROUTER_API_KEY", "stub")

    class _BoomProvider:
        name = "boom"
        supports_tools = True
        supports_streaming = True

        def create_message(self, *_a, **_kw):
            raise RuntimeError("network down")

    monkeypatch.setattr("veles.core.provider_factory.make_provider", lambda name: _BoomProvider())
    token = set_active_project(project)
    try:
        out = advisor_review("plan")
    finally:
        reset_active_project(token)
    assert "<advisor failed" in out
    assert "network down" in out


# ---------- routing default ----------


def test_advisor_default_routing_present() -> None:
    from veles.core.routing import DEFAULT_TASKS, parse_spec

    assert "advisor" in DEFAULT_TASKS
    provider, model = parse_spec(DEFAULT_TASKS["advisor"])
    assert provider
    assert model
