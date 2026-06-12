"""M125: curator now writes to SQL `insights` + `rules` tables, not
only to wiki markdown.

These tests verify the wiring:
- `_CURATE_TOOLS` now includes the M125 memory_save_* tools.
- The system prompt mentions both memory_save_insight and
  memory_save_rule (the agent gets actually told to use them).
- `_mirror_to_sql_insights` in insight_extractor uses the shared
  `save_insight_row` writer (end-to-end SQL bridge).

We don't run the LLM — verifying the prompt contents + tool tuple is
enough to demonstrate the agent will be steered to write SQL rows.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.cli._curator import _CURATE_TOOLS
from veles.core.context import reset_active_project, set_active_project
from veles.core.memory import SessionStore
from veles.core.project import init_project


@pytest.fixture()
def project(tmp_path: Path):
    proj = init_project(tmp_path / "proj", name="proj")
    token = set_active_project(proj)
    yield proj
    reset_active_project(token)


# ---- toolset registration ----


def test_curate_tools_include_memory_save() -> None:
    """M125: curator toolset must expose memory_save_insight AND
    memory_save_rule so the agent can land output in SQL."""
    assert "memory_save_insight" in _CURATE_TOOLS
    assert "memory_save_rule" in _CURATE_TOOLS


def test_curate_tools_retain_legacy_wiki_writers() -> None:
    """The bridge is additive — wiki_write_page + wiki_append_log stay
    so the wiki artefact survives alongside the SQL row."""
    assert "wiki_write_page" in _CURATE_TOOLS
    assert "wiki_append_log" in _CURATE_TOOLS


# ---- curator system prompt ----


def test_curate_prompt_instructs_memory_save_insight(project) -> None:
    """The curator system prompt must explicitly tell the agent to
    call memory_save_insight after writing the wiki page. Without
    this instruction the agent skips the SQL mirror."""
    from veles.cli._curator import _curate_one_session

    # We can't run _curate_one_session without an LLM, but we can
    # capture the system prompt by patching the Agent constructor.
    captured = {}

    class _FakeAgent:
        def __init__(self, **kwargs):
            captured["system_prompt"] = kwargs.get("system_prompt", "")

        def run(self, *a, **kw):
            from veles.core.agent import RunResult

            return RunResult(
                text="ok",
                history=[],
                iterations=1,
                stopped_reason="completed",
                session_id="x",
            )

    import veles.cli as cli_mod
    import veles.cli._curator as curator_mod
    from veles.core.memory import SessionInfo

    store = SessionStore(project.memory_db_path)
    sid = store.create_session()
    session_info = SessionInfo(
        id=sid, created_at=0.0, last_activity_at=0.0, title=None, turn_count=0
    )

    real_agent = curator_mod.Agent
    real_provider = cli_mod._make_tool_aware_provider
    real_skills = cli_mod._load_skills
    real_run = cli_mod._run_agent_streaming_aware
    real_qualify = cli_mod._qualify_for_provider
    try:
        curator_mod.Agent = _FakeAgent
        cli_mod._make_tool_aware_provider = lambda *a, **kw: None
        cli_mod._load_skills = lambda *a, **kw: None
        cli_mod._qualify_for_provider = lambda prompt, *a, **kw: prompt
        cli_mod._run_agent_streaming_aware = lambda *a, **kw: (
            type("R", (), {"stopped_reason": "completed"})(),
            None,
        )

        class _Args:
            provider = "openrouter"
            model = "x"
            max_iterations = 1
            verbose = False

        _curate_one_session(store, session_info, _Args(), project)
    finally:
        curator_mod.Agent = real_agent
        cli_mod._make_tool_aware_provider = real_provider
        cli_mod._load_skills = real_skills
        cli_mod._qualify_for_provider = real_qualify
        cli_mod._run_agent_streaming_aware = real_run
        store.close()

    prompt = captured["system_prompt"]
    assert "memory_save_insight" in prompt
    assert "memory_save_rule" in prompt
    assert "curated-session" in prompt
    # Honest about valid rule kinds
    assert "preference" in prompt
    assert "session-" in prompt


# ---- insight_extractor mirror uses the shared writer ----


def test_insight_extractor_imports_shared_save_writer() -> None:
    """`_mirror_to_sql_insights` must delegate to the shared
    `save_insight_row` helper from `memory_save.py` rather than
    re-implementing the INSERT. Code-level check: read the
    insight_extractor source and confirm the import landed."""
    import inspect

    import veles.core.insight_extractor as ie_mod

    source = inspect.getsource(ie_mod)
    assert "from veles.core.tools.builtin.memory_save import save_insight_row" in source
    # And the mirror function actually CALLS the shared writer
    assert "save_insight_row(" in source


def test_insight_extractor_mirror_writes_to_insights_table(project) -> None:
    """End-to-end: trigger the extractor with a stubbed sub-Agent
    whose .run() returns the canned extractor reply. The mirror runs
    inside `_persist_one` after `wiki.write_page` and lands a row
    in the SQL `insights` table via `save_insight_row`."""
    from unittest.mock import patch

    from tests.conftest import StubProvider
    from veles.core.agent import RunResult
    from veles.core.insight_extractor import make_insight_extractor
    from veles.core.provider import Message, ProviderResponse, TokenUsage

    stub_provider = StubProvider(
        [
            ProviderResponse(
                text="slug: real-db-rule\nbody: always use real DB",
                tool_calls=[],
                usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                finish_reason="stop",
            )
        ],
        supports_tools=False,
        repeat_last=True,
    )

    class _StubAgent:
        def __init__(self, **kwargs):
            pass

        def run(self, snippet):
            return RunResult(
                text="slug: real-db-rule\nbody: always use real DB in tests",
                history=[],
                iterations=1,
                stopped_reason="completed",
                session_id=None,
            )

    extractor = make_insight_extractor(provider=stub_provider, model="x", project=project)

    fake_history = [
        Message(role="user", content="please remember: always use real DB in tests"),
        Message(role="assistant", content="noted"),
    ]
    # Patch Agent where insight_extractor binds it via lazy import.
    with patch("veles.core.agent.Agent", _StubAgent):
        extractor(fake_history, "test-session")

    store = SessionStore(project.memory_db_path)
    rows = store._conn.execute("SELECT title, body, category FROM insights").fetchall()
    store._conn.close()
    assert rows, "expected at least one SQL insight row from extractor mirror"
    # Categories track the trigger label ("remember", "recovery")
    cats = [r["category"] for r in rows]
    assert any("remember" in (c or "") for c in cats), (
        f"expected remember-trigger category, got {cats}"
    )
