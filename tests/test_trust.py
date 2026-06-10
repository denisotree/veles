"""M38 — trust ladder evaluation + Agent dispatch integration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.conftest import StubProvider as _StubProvider
from veles.core.agent import Agent
from veles.core.context import (
    reset_active_project,
    set_active_project,
)
from veles.core.permission.prompt import (
    PromptAnswer,
    PromptRequest,
    reset_prompter as reset_unified_prompter,
    set_prompter as set_unified_prompter,
)
from veles.core.project import init_project
from veles.core.provider import ProviderResponse, TokenUsage, ToolCall
from veles.core.tools.registry import Registry, ToolEntry
from veles.core.trust import (
    TrustChoice,
    TrustDecision,
    _default_prompter,
    _parse_choice,
    begin_trust_turn,
    end_trust_turn,
    evaluate_trust,
)
from veles.core.trust_store import TrustStore

# ---------- harness ----------

_CHOICE_TO_DECISION = {
    TrustChoice.ONCE: "allow_once",
    TrustChoice.ALWAYS_PROJECT: "allow_project",
    TrustChoice.ALWAYS_GLOBAL: "allow_global",
    TrustChoice.REFUSE: "deny",
}


def _install_trust(choice: TrustChoice):
    """Install a unified prompter that always answers with `choice`.
    Returns the ContextVar token for `reset_unified_prompter`."""
    return set_unified_prompter(
        lambda _req: PromptAnswer(_CHOICE_TO_DECISION[choice])  # type: ignore[arg-type]
    )


def _ok(text: str = "done") -> ProviderResponse:
    return ProviderResponse(
        text=text,
        tool_calls=[],
        usage=TokenUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
        finish_reason="stop",
    )


def _call(name: str, args: dict[str, Any]) -> ProviderResponse:
    return ProviderResponse(
        text=None,
        tool_calls=[ToolCall(id="c1", name=name, arguments=args)],
        usage=TokenUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
        finish_reason="tool_use",
    )


def _registry_with(*entries: ToolEntry) -> Registry:
    reg = Registry()
    for e in entries:
        reg.register(e)
    return reg


def _sensitive_tool(name: str = "danger") -> ToolEntry:
    return ToolEntry(
        name=name,
        description="dangerous op",
        parameter_schema={"type": "object", "properties": {}},
        handler=lambda **_: f"{name}-ran",
        is_async=False,
        sensitive=True,
    )


def _safe_tool(name: str = "echo") -> ToolEntry:
    return ToolEntry(
        name=name,
        description="safe op",
        parameter_schema={"type": "object", "properties": {}},
        handler=lambda **_: f"{name}-ran",
        is_async=False,
        sensitive=False,
    )


@pytest.fixture(autouse=True)
def _isolate_user_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Redirect ~/.veles to a tmp dir AND clear any leaked active project."""
    isolated = tmp_path / "_user_home"
    isolated.mkdir()
    monkeypatch.setenv("VELES_USER_HOME", str(isolated))
    monkeypatch.delenv("VELES_TRUST_AUTO_ALLOW", raising=False)
    # An earlier test (e.g. test_path_guard) may have left an active project
    # in the ContextVar. Reset it so test cases that don't set their own
    # project see a clean slate.
    reset_token = set_active_project(None)
    yield
    reset_active_project(reset_token)


# ---------- evaluate_trust ----------


def test_auto_allow_env_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VELES_TRUST_AUTO_ALLOW", "1")
    assert evaluate_trust("run_shell") == TrustDecision(allowed=True, reason="auto-allow")


def test_user_scope_grant_is_silent_allow() -> None:
    from veles.core.trust_store import user_trust_path

    user_path = user_trust_path()
    user_path.parent.mkdir(parents=True, exist_ok=True)
    TrustStore.load(user_path).grant("run_shell")
    decision = evaluate_trust("run_shell")
    assert decision.allowed
    assert "user-scope" in decision.reason


def test_project_scope_grant_is_silent_allow(tmp_path: Path) -> None:
    project = init_project(tmp_path / "proj", name="proj")
    TrustStore.load(project.trust_path).grant("run_shell")
    token = set_active_project(project)
    try:
        decision = evaluate_trust("run_shell")
    finally:
        reset_active_project(token)
    assert decision.allowed
    assert "project-scope" in decision.reason


def test_prompt_once_allows_without_persisting(tmp_path: Path) -> None:
    project = init_project(tmp_path / "proj", name="proj")
    proj_token = set_active_project(project)
    p_token = _install_trust(TrustChoice.ONCE)
    try:
        decision = evaluate_trust("run_shell")
    finally:
        reset_unified_prompter(p_token)
        reset_active_project(proj_token)
    assert decision.allowed
    assert "once" in decision.reason
    assert not TrustStore.load(project.trust_path).is_granted("run_shell")


def test_prompt_always_project_persists_to_project_file(tmp_path: Path) -> None:
    project = init_project(tmp_path / "proj", name="proj")
    proj_token = set_active_project(project)
    p_token = _install_trust(TrustChoice.ALWAYS_PROJECT)
    try:
        decision = evaluate_trust("run_shell")
    finally:
        reset_unified_prompter(p_token)
        reset_active_project(proj_token)
    assert decision.allowed
    assert "project" in decision.reason
    assert TrustStore.load(project.trust_path).is_granted("run_shell")
    # Not persisted to user-scope.
    from veles.core.trust_store import user_trust_path

    assert not TrustStore.load(user_trust_path()).is_granted("run_shell")


def test_prompt_always_global_persists_to_user_file() -> None:
    p_token = _install_trust(TrustChoice.ALWAYS_GLOBAL)
    try:
        decision = evaluate_trust("run_shell")
    finally:
        reset_unified_prompter(p_token)
    assert decision.allowed
    from veles.core.trust_store import user_trust_path

    assert TrustStore.load(user_trust_path()).is_granted("run_shell")


def test_prompt_refuse_blocks() -> None:
    p_token = _install_trust(TrustChoice.REFUSE)
    try:
        decision = evaluate_trust("run_shell")
    finally:
        reset_unified_prompter(p_token)
    assert not decision.allowed
    assert "refused" in decision.reason


def test_always_project_without_active_project_is_one_off() -> None:
    """With no active project, ALWAYS_PROJECT degrades to a once-grant."""
    p_token = _install_trust(TrustChoice.ALWAYS_PROJECT)
    try:
        decision = evaluate_trust("run_shell")
    finally:
        reset_unified_prompter(p_token)
    assert decision.allowed
    assert "no active project" in decision.reason


def test_prompter_exception_refuses() -> None:
    def bad(_req: PromptRequest) -> PromptAnswer:
        raise RuntimeError("kaboom")

    p_token = set_unified_prompter(bad)
    try:
        decision = evaluate_trust("run_shell")
    finally:
        reset_unified_prompter(p_token)
    assert not decision.allowed
    assert "kaboom" in decision.reason


def test_default_prompter_refuses_without_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pytest stdin is not a TTY; the default prompter must refuse silently."""
    # Make absolutely sure isatty() returns False even on some runners.
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert _default_prompter("run_shell") is TrustChoice.REFUSE


def test_parse_choice_recognises_aliases() -> None:
    assert _parse_choice("1") is TrustChoice.ONCE
    assert _parse_choice("once") is TrustChoice.ONCE
    assert _parse_choice("2") is TrustChoice.ALWAYS_PROJECT
    assert _parse_choice("3") is TrustChoice.ALWAYS_GLOBAL
    assert _parse_choice("4") is TrustChoice.REFUSE
    assert _parse_choice("") is TrustChoice.REFUSE
    assert _parse_choice("garbage") is TrustChoice.REFUSE


# ---------- _dispatch integration ----------


def test_dispatch_blocks_sensitive_when_refused() -> None:
    reg = _registry_with(_sensitive_tool("danger"))
    provider = _StubProvider(responses=[_call("danger", {}), _ok("survived")])
    agent = Agent(provider=provider, registry=reg, model="m")
    p_token = _install_trust(TrustChoice.REFUSE)
    try:
        result = agent.run("run danger")
    finally:
        reset_unified_prompter(p_token)
    tool_msg = next(m for m in result.history if m.role == "tool")
    # M64: refusal message now carries the machine-stable rule discriminator
    # (`trust_ladder`) so events.jsonl filters keep working.
    assert "refused by trust_ladder" in tool_msg.content
    # Subsequent assistant turn proceeds (final response is from second stub).
    assert result.text == "survived"


def test_dispatch_allows_sensitive_when_granted_via_prompt() -> None:
    reg = _registry_with(_sensitive_tool("danger"))
    provider = _StubProvider(responses=[_call("danger", {}), _ok("ok")])
    agent = Agent(provider=provider, registry=reg, model="m")
    p_token = _install_trust(TrustChoice.ONCE)
    try:
        result = agent.run("run danger")
    finally:
        reset_unified_prompter(p_token)
    tool_msg = next(m for m in result.history if m.role == "tool")
    assert tool_msg.content == "danger-ran"


def test_dispatch_skips_check_for_non_sensitive_tool() -> None:
    """Non-sensitive tools must dispatch without invoking the prompter."""
    reg = _registry_with(_safe_tool("echo"))
    provider = _StubProvider(responses=[_call("echo", {}), _ok("ok")])
    agent = Agent(provider=provider, registry=reg, model="m")
    invocations: list[str] = []

    def boom(req: PromptRequest) -> PromptAnswer:
        invocations.append(req.tool_name)
        raise AssertionError("prompter should not run for non-sensitive tools")

    p_token = set_unified_prompter(boom)
    try:
        result = agent.run("echo")
    finally:
        reset_unified_prompter(p_token)
    assert invocations == []
    tool_msg = next(m for m in result.history if m.role == "tool")
    assert tool_msg.content == "echo-ran"


def test_dispatch_uses_existing_grant_no_prompt(tmp_path: Path) -> None:
    """Grant in user-scope file → dispatch silently, prompter not invoked."""
    from veles.core.trust_store import user_trust_path

    TrustStore.load(user_trust_path()).grant("danger")
    reg = _registry_with(_sensitive_tool("danger"))
    provider = _StubProvider(responses=[_call("danger", {}), _ok("ok")])
    agent = Agent(provider=provider, registry=reg, model="m")
    invocations: list[str] = []
    p_token = set_unified_prompter(
        lambda req: invocations.append(req.tool_name) or PromptAnswer("deny")  # type: ignore[func-returns-value]
    )
    try:
        result = agent.run("run danger")
    finally:
        reset_unified_prompter(p_token)
    assert invocations == []
    tool_msg = next(m for m in result.history if m.role == "tool")
    assert tool_msg.content == "danger-ran"


def test_module_veto_short_circuits_before_trust() -> None:
    """If a module veto fires in pre_tool_call, trust prompter must NOT run."""
    from veles.core.modules import (
        ModuleRegistry,
        VetoResult,
        reset_module_registry,
        set_module_registry,
    )

    reg = _registry_with(_sensitive_tool("danger"))
    provider = _StubProvider(responses=[_call("danger", {}), _ok("ok")])
    agent = Agent(provider=provider, registry=reg, model="m")
    mod_reg = ModuleRegistry()
    mod_reg.add_hook("pre_tool_call", "blocker", lambda ctx: VetoResult(reason="nope"))
    invocations: list[str] = []

    def prompter(req: PromptRequest) -> PromptAnswer:
        invocations.append(req.tool_name)
        return PromptAnswer("allow_once")

    p_token = set_unified_prompter(prompter)
    m_token = set_module_registry(mod_reg)
    try:
        result = agent.run("run danger")
    finally:
        reset_unified_prompter(p_token)
        reset_module_registry(m_token)
    assert invocations == []
    tool_msg = next(m for m in result.history if m.role == "tool")
    assert "vetoed by module" in tool_msg.content


def test_once_grant_reused_within_turn() -> None:
    """ONCE within an active turn scope silently allows subsequent calls."""
    call_count: list[int] = [0]

    def counting_prompter(_req: PromptRequest) -> PromptAnswer:
        call_count[0] += 1
        return PromptAnswer("allow_once")

    p_token = set_unified_prompter(counting_prompter)
    turn_token = begin_trust_turn()
    try:
        d1 = evaluate_trust("run_shell")
        d2 = evaluate_trust("run_shell")
    finally:
        end_trust_turn(turn_token)
        reset_unified_prompter(p_token)

    assert d1.allowed and d2.allowed
    assert call_count[0] == 1, "prompter called more than once within turn"
    assert "turn" in d2.reason


def test_once_grant_not_reused_outside_turn() -> None:
    """Without an active turn scope, each ONCE call prompts individually."""
    call_count: list[int] = [0]

    def counting_prompter(_req: PromptRequest) -> PromptAnswer:
        call_count[0] += 1
        return PromptAnswer("allow_once")

    p_token = set_unified_prompter(counting_prompter)
    try:
        d1 = evaluate_trust("run_shell")
        d2 = evaluate_trust("run_shell")
    finally:
        reset_unified_prompter(p_token)

    assert d1.allowed and d2.allowed
    assert call_count[0] == 2, "prompter should be called for each call without turn scope"
