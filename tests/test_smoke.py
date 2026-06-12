"""End-to-end smoke tests against real OpenRouter API.

Skipped unless `VELES_LIVE_TESTS=1` and `OPENROUTER_API_KEY` are set in env.
Each smoke test creates a Project in tmp_path and activates it via ContextVar
so wiki tools see the right root.
"""

from __future__ import annotations

import os

import pytest

from veles.adapters.openrouter import OpenRouterProvider
from veles.core.agent import Agent
from veles.core.context import reset_active_project, set_active_project
from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.core.tools import registry

_LIVE = os.environ.get("VELES_LIVE_TESTS") == "1" and bool(os.environ.get("OPENROUTER_API_KEY"))
_DEFAULT_MODEL = os.environ.get("VELES_TEST_MODEL", "anthropic/claude-sonnet-4.6")
_SKIP_REASON = "set VELES_LIVE_TESTS=1 and OPENROUTER_API_KEY to enable"


@pytest.fixture
def project(tmp_path):
    """Initialize a fresh Veles project in tmp_path and activate it."""
    p = init_project(tmp_path, name="smoke")
    token = set_active_project(p)
    try:
        yield p
    finally:
        reset_active_project(token)


@pytest.mark.skipif(not _LIVE, reason=_SKIP_REASON)
def test_read_task_md_smoke(project):
    """The agent reads the on-disk TASK.md (in the cwd of pytest, not tmp_path)."""
    provider = OpenRouterProvider()
    agent = Agent(
        provider=provider,
        registry=registry,
        model=_DEFAULT_MODEL,
        max_iterations=10,
    )
    result = agent.run(
        "Read TASK.md (it lives in the current working directory) "
        "and tell me in one sentence what Veles is."
    )
    assert result.text, "agent returned empty text"
    assert "Veles" in result.text, f"answer should mention Veles; got: {result.text!r}"
    used_read_file = any(
        m.role == "assistant" and any(tc.name == "read_file" for tc in m.tool_calls)
        for m in result.history
    )
    assert used_read_file, "agent should have called read_file"


@pytest.mark.skipif(not _LIVE, reason=_SKIP_REASON)
def test_resume_smoke(project):
    provider = OpenRouterProvider()
    store = SessionStore(project.memory_db_path)
    try:
        first_agent = Agent(
            provider=provider,
            registry=registry,
            model=_DEFAULT_MODEL,
            max_iterations=5,
            store=store,
        )
        first = first_agent.run(
            "Please remember: my favourite colour is purple. Acknowledge briefly."
        )
        sid = first.session_id
        assert sid is not None

        second_agent = Agent(
            provider=provider,
            registry=registry,
            model=_DEFAULT_MODEL,
            max_iterations=5,
            store=store,
            session_id=sid,
        )
        second = second_agent.run(
            "What did I tell you my favourite colour was? Answer with one word."
        )
        assert second.session_id == sid
        assert "purple" in second.text.lower(), (
            f"agent failed to recall colour; answer was {second.text!r}"
        )
        all_msgs = store.load_messages(sid)
        user_contents = [m.content for m in all_msgs if m.role == "user"]
        assert len(user_contents) == 2
        assert "purple" in user_contents[0].lower()
    finally:
        store.close()
