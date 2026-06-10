"""M114: Agent refreshes its system message when resuming a session
with a fresh `system_prompt` from the caller.

Before the fix, `_bootstrap_history` returned the stored history
verbatim on resume — the Telegram bot kept seeing the model with the
system message frozen at the first turn, so AGENTS.md changes / recall
updates / subproject proposals never reached subsequent turns.
"""

from __future__ import annotations

from tests.conftest import StubProvider
from veles.core.agent import Agent
from veles.core.memory import SessionStore
from veles.core.provider import Message


def _make_agent(*, session_id=None, system_prompt=None, store=None) -> Agent:
    from veles.core.tools.registry import Registry

    return Agent(
        # No scripted responses: any provider call raises — these tests
        # never run a turn, just bootstrap history.
        provider=StubProvider(supports_tools=False),  # type: ignore[arg-type]
        registry=Registry(),
        model="m",
        store=store,
        session_id=session_id,
        system_prompt=system_prompt,
    )


def test_fresh_session_persists_initial_system_prompt() -> None:
    store = SessionStore(":memory:")
    try:
        agent = _make_agent(system_prompt="INITIAL", store=store)
        history = agent._bootstrap_history()
        assert history[0].role == "system"
        assert history[0].content == "INITIAL"
        # Reload from disk: persistence is intact.
        sid = agent.session_id
        assert sid is not None
        stored = store.load_messages(sid)
        assert stored[0].content == "INITIAL"
    finally:
        store.close()


def test_resume_with_new_system_prompt_replaces_in_history() -> None:
    """The exact scenario the Telegram bot trips on: same session_id
    across two turns, a fresh `system_prompt` on the second build."""
    store = SessionStore(":memory:")
    try:
        # First turn — seed the session with an initial system message.
        agent1 = _make_agent(system_prompt="OLD-AGENTS-MD", store=store)
        agent1._bootstrap_history()
        sid = agent1.session_id
        assert sid is not None

        # Second turn — same session, different system prompt (e.g.
        # AGENTS.md changed, or recall pulled new wiki pages).
        agent2 = _make_agent(
            session_id=sid, system_prompt="FRESH-AGENTS-MD", store=store
        )
        history = agent2._bootstrap_history()
        assert history[0].role == "system"
        assert history[0].content == "FRESH-AGENTS-MD"
    finally:
        store.close()


def test_resume_without_system_prompt_keeps_stored_one() -> None:
    """`veles run --resume <id>` passes `system_prompt=None` to honour
    the original session context — that path must still work."""
    store = SessionStore(":memory:")
    try:
        agent1 = _make_agent(system_prompt="ORIGINAL", store=store)
        agent1._bootstrap_history()
        sid = agent1.session_id
        assert sid is not None

        agent2 = _make_agent(session_id=sid, system_prompt=None, store=store)
        history = agent2._bootstrap_history()
        assert history[0].role == "system"
        assert history[0].content == "ORIGINAL"
    finally:
        store.close()


def test_resume_with_no_stored_system_prepends_fresh() -> None:
    """Edge case: an older session that never persisted a system
    message (legacy fresh-only path with empty prompt). Resuming with
    a fresh `system_prompt` should still inject it at the head."""
    store = SessionStore(":memory:")
    try:
        sid = store.create_session()
        # Manually seed history with a user message only — no system.
        store.append_turn(sid, Message(role="user", content="hi"))

        agent = _make_agent(
            session_id=sid, system_prompt="FRESH", store=store
        )
        history = agent._bootstrap_history()
        assert history[0].role == "system"
        assert history[0].content == "FRESH"
        # And the original user message is still there.
        assert any(m.role == "user" and m.content == "hi" for m in history)
    finally:
        store.close()
