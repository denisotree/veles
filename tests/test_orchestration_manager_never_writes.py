"""M122c: runtime "manager-never-writes" guards (VISION §5.3).

The plan-level guard (`assert_plan_valid`) already rejects plans with no
writer / a manager step. These are the runtime backstops one level down:
`Agent.run` refuses to run a `role="manager"` agent, and `spawn("manager", …)`
returns an error handle without ever constructing/running an agent.
"""

from __future__ import annotations

import pytest

from tests.conftest import StubProvider
from veles.core.agent import Agent, ManagerNeverWritesError
from veles.core.orchestration import spawn
from veles.core.provider import ProviderResponse, TokenUsage
from veles.core.tools.registry import Registry


def _stub_provider() -> StubProvider:
    return StubProvider(
        [
            ProviderResponse(
                text="should never be reached",
                tool_calls=[],
                usage=TokenUsage(
                    prompt_tokens=1, completion_tokens=1, total_tokens=2
                ),
                finish_reason="stop",
            )
        ],
        repeat_last=True,
    )


# ---- Agent.run guard ----


def test_manager_role_agent_run_raises():
    agent = Agent(_stub_provider(), Registry(), model="m", role="manager")
    with pytest.raises(ManagerNeverWritesError):
        agent.run("write the final answer")


def test_default_role_is_none_and_runs():
    """No role (the default) must not trip the guard — a plain agent runs."""
    agent = Agent(_stub_provider(), Registry(), model="m")
    result = agent.run("hello")
    assert result.text == "should never be reached"  # i.e. the run proceeded


def test_explorer_role_agent_runs():
    agent = Agent(_stub_provider(), Registry(), model="m", role="explorer")
    assert agent.run("gather evidence").text == "should never be reached"


# ---- spawn guard ----


def test_spawn_manager_returns_error_without_constructing():
    calls: list[dict] = []

    def factory(**kwargs):
        calls.append(kwargs)
        raise AssertionError("factory must not be called for a manager spawn")

    handle = spawn("manager", "do everything", agent_factory=factory)
    assert handle.result is None
    assert "manager-never-writes" in (handle.error or "")
    assert calls == []  # factory never invoked


def test_spawn_explorer_still_constructs():
    constructed: list[dict] = []

    class _A:
        def __init__(self, **kwargs):
            constructed.append(kwargs)

        def run(self, prompt):
            return type("R", (), {"text": f"ran: {prompt}", "session_id": "s1", "usage": None})()

    handle = spawn("explorer", "look", agent_factory=lambda **kw: _A(**kw))
    assert handle.error is None
    assert handle.result == "ran: look"
    assert len(constructed) == 1
