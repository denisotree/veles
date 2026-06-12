"""M122d: opt-in production seam for the manager orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from veles.core.orchestration import (
    MANAGER_ENV,
    env_manager_mode,
    run_with_manager_if_eligible,
    should_use_manager,
)

# ---- env_manager_mode ----


def test_env_manager_unset_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(MANAGER_ENV, raising=False)
    assert env_manager_mode() is None


def test_env_manager_truthy_values_return_true(monkeypatch: pytest.MonkeyPatch) -> None:
    for v in ("1", "true", "True", "ON", "yes"):
        monkeypatch.setenv(MANAGER_ENV, v)
        assert env_manager_mode() is True, v


def test_env_manager_falsy_values_return_false(monkeypatch: pytest.MonkeyPatch) -> None:
    for v in ("0", "false", "FALSE", "off", "no"):
        monkeypatch.setenv(MANAGER_ENV, v)
        assert env_manager_mode() is False, v


def test_env_manager_unrecognised_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(MANAGER_ENV, "maybe")
    assert env_manager_mode() is None


# ---- should_use_manager ----


def test_should_use_manager_force_true_overrides_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(MANAGER_ENV, "0")
    assert should_use_manager("short", force=True) is True


def test_should_use_manager_force_false_overrides_heuristic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(MANAGER_ENV, raising=False)
    # Long prompt would normally trigger heuristic
    long_prompt = "research the codebase " * 10
    assert should_use_manager(long_prompt, force=False) is False


def test_should_use_manager_env_true_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(MANAGER_ENV, "1")
    # Short prompt would normally NOT trigger heuristic
    assert should_use_manager("x") is True


def test_should_use_manager_env_false_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(MANAGER_ENV, "0")
    # Even a research-keyword prompt is blocked by env=false
    assert should_use_manager("research the project") is False


def test_should_use_manager_heuristic_when_env_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(MANAGER_ENV, raising=False)
    assert should_use_manager("short") is False
    assert should_use_manager("research the project") is True


# ---- run_with_manager_if_eligible ----


@dataclass
class _FakeUsage:
    prompt_tokens: int = 5
    completion_tokens: int = 5


@dataclass
class _FakeResult:
    text: str
    session_id: str = "s1"
    usage: _FakeUsage = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.usage is None:
            self.usage = _FakeUsage()


class _StubAgent:
    def __init__(self, *, system_prompt: str | None = None) -> None:
        self.system_prompt = system_prompt or ""

    def run(self, prompt: str) -> _FakeResult:
        role = (
            "writer"
            if "writer worker" in self.system_prompt
            else ("explorer" if "explorer worker" in self.system_prompt else "other")
        )
        return _FakeResult(text=f"[{role}] head: {prompt[:40]}", session_id="s")


def _factory(**kwargs: Any) -> _StubAgent:
    return _StubAgent(system_prompt=kwargs.get("system_prompt"))


def test_direct_runner_called_when_not_eligible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(MANAGER_ENV, raising=False)
    captured: list[str] = []

    def direct(prompt: str) -> str:
        captured.append(prompt)
        return f"direct: {prompt}"

    out = run_with_manager_if_eligible("short", agent_factory=_factory, direct_runner=direct)
    assert out == "direct: short"
    assert captured == ["short"]


def test_manager_runner_called_when_eligible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(MANAGER_ENV, raising=False)
    direct_calls: list[str] = []

    def direct(prompt: str) -> str:
        direct_calls.append(prompt)
        return "direct"

    out = run_with_manager_if_eligible(
        "research the codebase deeply",
        agent_factory=_factory,
        direct_runner=direct,
    )
    # Manager path used — direct runner not called
    assert direct_calls == []
    # Returned text from writer worker
    assert out is not None
    assert "[writer]" in out


def test_force_true_routes_to_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(MANAGER_ENV, raising=False)
    direct_calls: list[str] = []

    def direct(prompt: str) -> str:
        direct_calls.append(prompt)
        return "direct"

    out = run_with_manager_if_eligible(
        "x",  # short, would default to direct
        agent_factory=_factory,
        direct_runner=direct,
        force=True,
    )
    assert direct_calls == []
    assert out is not None
    assert "[writer]" in out


def test_force_false_routes_to_direct(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(MANAGER_ENV, raising=False)
    captured: list[str] = []

    def direct(prompt: str) -> str:
        captured.append(prompt)
        return "direct"

    out = run_with_manager_if_eligible(
        "research the codebase",
        agent_factory=_factory,
        direct_runner=direct,
        force=False,
    )
    assert captured == ["research the codebase"]
    assert out == "direct"


def test_env_var_routes_to_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(MANAGER_ENV, "1")
    direct_calls: list[str] = []

    def direct(prompt: str) -> str:
        direct_calls.append(prompt)
        return "direct"

    out = run_with_manager_if_eligible(
        "anything short", agent_factory=_factory, direct_runner=direct
    )
    assert direct_calls == []
    assert out is not None


def test_manager_failure_falls_back_to_direct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If decompose_and_run reports an error, the helper falls
    through to the direct runner instead of returning None."""
    monkeypatch.setenv(MANAGER_ENV, "1")

    class _BadAgent:
        def __init__(self, **_kw: Any) -> None:
            pass

        def run(self, _prompt: str):
            raise RuntimeError("agent down")

    def bad_factory(**_kw: Any) -> _BadAgent:
        return _BadAgent()

    direct_calls: list[str] = []

    def direct(prompt: str) -> str:
        direct_calls.append(prompt)
        return "fallback"

    out = run_with_manager_if_eligible("anything", agent_factory=bad_factory, direct_runner=direct)
    assert direct_calls == ["anything"]
    assert out == "fallback"
