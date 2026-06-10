"""Unit tests for cumulative token budget tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from veles.core.agent import Agent
from veles.core.context import (
    TokenBudget,
    current_budget,
    reset_budget,
    set_budget,
)
from veles.core.project import init_project
from veles.core.provider import ProviderResponse, TokenUsage
from veles.core.skills import discover_skills, make_skill_tool
from veles.core.tools.registry import Registry


@dataclass
class _BudgetStubProvider:
    """Stub provider returning fixed TokenUsage on every call."""

    name: str = "budget-stub"
    supports_tools: bool = True
    tokens_per_call: int = 100
    reply: str = "ok"
    calls: list[Any] = field(default_factory=list)

    def create_message(
        self, messages, tools=None, *, model: str, max_tokens: int = 4096
    ) -> ProviderResponse:
        self.calls.append(model)
        return ProviderResponse(
            text=self.reply,
            tool_calls=[],
            usage=TokenUsage(
                prompt_tokens=self.tokens_per_call // 2,
                completion_tokens=self.tokens_per_call // 2,
                total_tokens=self.tokens_per_call,
            ),
            finish_reason="stop",
        )


def test_token_budget_remaining_returns_negative_for_unlimited() -> None:
    b = TokenBudget(limit=0)
    assert b.remaining == -1
    assert b.exhausted is False


def test_token_budget_exhausted_property() -> None:
    b = TokenBudget(limit=100, consumed=99)
    assert b.exhausted is False
    b.consumed = 100
    assert b.exhausted is True
    b.consumed = 101
    assert b.exhausted is True


def test_set_reset_budget_helpers() -> None:
    assert current_budget() is None
    b = TokenBudget(limit=50)
    token = set_budget(b)
    try:
        assert current_budget() is b
    finally:
        reset_budget(token)
    assert current_budget() is None


def test_budget_tracks_consumed_after_provider_call() -> None:
    provider = _BudgetStubProvider(tokens_per_call=42)
    agent = Agent(
        provider=provider,
        registry=Registry(),
        model="m",
        max_iterations=1,
    )
    budget = TokenBudget(limit=1000)
    token = set_budget(budget)
    try:
        agent.run("hello")
    finally:
        reset_budget(token)
    assert budget.consumed == 42
    assert budget.exhausted is False


def test_budget_zero_limit_is_unlimited() -> None:
    provider = _BudgetStubProvider(tokens_per_call=1_000_000)
    agent = Agent(provider=provider, registry=Registry(), model="m", max_iterations=1)
    budget = TokenBudget(limit=0)
    token = set_budget(budget)
    try:
        result = agent.run("hi")
    finally:
        reset_budget(token)
    assert result.stopped_reason == "completed"
    assert budget.consumed == 1_000_000
    assert budget.exhausted is False


def test_no_budget_means_no_tracking() -> None:
    provider = _BudgetStubProvider(tokens_per_call=100)
    agent = Agent(provider=provider, registry=Registry(), model="m", max_iterations=1)
    # current_budget() is None by default
    result = agent.run("hi")
    assert result.stopped_reason == "completed"


def test_budget_exhausted_stops_run_before_call() -> None:
    provider = _BudgetStubProvider(tokens_per_call=100)
    agent = Agent(provider=provider, registry=Registry(), model="m", max_iterations=5)
    budget = TokenBudget(limit=10, consumed=10)  # already exhausted
    token = set_budget(budget)
    try:
        result = agent.run("anything")
    finally:
        reset_budget(token)
    assert result.stopped_reason == "budget_exhausted"
    assert provider.calls == []  # no provider invocation
    assert "budget exhausted" in result.text


def test_budget_exhausts_mid_iteration_chain() -> None:
    """First turn fits, second turn would exceed → second never runs."""

    @dataclass
    class _RetryStub:
        name: str = "retry-stub"
        supports_tools: bool = True
        calls: list[Any] = field(default_factory=list)

        def create_message(self, messages, tools=None, *, model, max_tokens=4096):
            self.calls.append(model)
            # Always emit a tool_call so the loop continues to a second turn.
            from veles.core.provider import ToolCall

            return ProviderResponse(
                text=None,
                tool_calls=[ToolCall(id=f"c{len(self.calls)}", name="noop", arguments={})],
                usage=TokenUsage(prompt_tokens=50, completion_tokens=50, total_tokens=100),
            )

    provider = _RetryStub()
    registry = Registry()

    # Register a noop tool so dispatch doesn't error.
    from veles.core.tools.registry import ToolEntry

    registry.register(
        ToolEntry(
            name="noop",
            description="returns ok",
            parameter_schema={"type": "object", "properties": {}},
            handler=lambda **_: "ok",
            is_async=False,
        )
    )

    agent = Agent(provider=provider, registry=registry, model="m", max_iterations=10)
    # Agent checks `exhausted` at the start of each turn. With limit=150 and
    # 100 tokens/call: turn 1 (consumed 0<150) → call → 100. Turn 2 (100<150)
    # → call → 200. Turn 3 (200>=150) → refuse. So the agent makes 2 calls
    # before the budget short-circuits the loop.
    budget = TokenBudget(limit=150)
    token = set_budget(budget)
    try:
        result = agent.run("loop forever")
    finally:
        reset_budget(token)
    assert len(provider.calls) == 2
    assert budget.consumed == 200
    assert result.stopped_reason == "budget_exhausted"


def test_budget_propagates_to_subagent(tmp_path: Path) -> None:
    """A skill's sub-agent shares the parent's budget via ContextVar."""
    project = init_project(tmp_path, name="t")
    skill_dir = project.skills_dir / "echo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: echo\ndescription: e\ntools: []\nuse_count: 0\n---\nbody",
        encoding="utf-8",
    )
    skill = discover_skills(project)[0]
    provider = _BudgetStubProvider(tokens_per_call=42)
    base_registry = Registry()
    entry = make_skill_tool(skill, provider=provider, model="m", base_registry=base_registry)

    budget = TokenBudget(limit=1000)
    token = set_budget(budget)
    try:
        # Top-level agent doesn't run; we directly invoke the skill handler.
        # Sub-agent inside should see and increment the same budget.
        entry.handler(input="x")
    finally:
        reset_budget(token)
    # Sub-agent ran one turn → 42 tokens consumed in the shared budget.
    assert budget.consumed == 42


def test_budget_exhausted_returns_correct_run_result() -> None:
    provider = _BudgetStubProvider(tokens_per_call=100)
    agent = Agent(provider=provider, registry=Registry(), model="m", max_iterations=5)
    budget = TokenBudget(limit=50, consumed=50)
    token = set_budget(budget)
    try:
        result = agent.run("hi")
    finally:
        reset_budget(token)
    assert result.stopped_reason == "budget_exhausted"
    assert "50/50" in result.text
    assert result.iterations == 0
