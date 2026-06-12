"""Daemon's agent_factory must assemble a system prompt the same way
`veles run` does — AGENTS.md included.

We mock the helpers that the factory imports lazily from `veles.cli`
so we don't need the network or a real Agent.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import veles.cli as cli_mod
import veles.core.agent as agent_mod
from tests.conftest import StubProvider
from veles.cli.commands.daemon import _make_agent_factory
from veles.core.context import reset_active_project, set_active_project
from veles.core.memory import SessionStore
from veles.core.project import init_project


def _build_args() -> argparse.Namespace:
    return argparse.Namespace(
        provider="openrouter",
        model="anthropic/claude-sonnet-4.6",
        max_iterations=1,
        max_tokens=4096,
        verbose=False,
        no_compress=True,
    )


def _install_factory_stubs(monkeypatch) -> dict:
    """Patch the helpers `_make_agent_factory.factory` imports from
    `veles.cli`. Returns the dict that Agent.__init__ captures."""
    from veles.core.tools.registry import Registry

    captured: dict = {}

    class _StubAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(
        cli_mod,
        "_make_provider",
        lambda *_a, **_kw: StubProvider(supports_tools=False, supports_streaming=True),
    )
    monkeypatch.setattr(cli_mod, "_load_skills", lambda *_a, **_kw: Registry())
    monkeypatch.setattr(cli_mod, "_build_compressor", lambda *_a, **_kw: None)
    monkeypatch.setattr(agent_mod, "Agent", _StubAgent)
    return captured


def test_fresh_session_injects_agents_md(tmp_path: Path, monkeypatch) -> None:
    project = init_project(tmp_path, name="pjtest")
    token = set_active_project(project)
    try:
        (project.root / "AGENTS.md").write_text(
            "# Test Project\n\nSENTINEL_MARKER_FROM_AGENTS_MD\n", encoding="utf-8"
        )
        store = SessionStore(project.memory_db_path)
        captured = _install_factory_stubs(monkeypatch)

        factory = _make_agent_factory(_build_args(), project=project, store=store)
        factory(None, prompt="hello")

        sp = captured.get("system_prompt") or ""
        assert "SENTINEL_MARKER_FROM_AGENTS_MD" in sp
        assert captured.get("model") == "anthropic/claude-sonnet-4.6"
    finally:
        reset_active_project(token)


def test_daemon_system_prompt_isolates_subproject(tmp_path: Path, monkeypatch) -> None:
    """Mind Palace bug: the channel-run system prompt must not leak

    1. other subprojects' proposals,
    2. absolute filesystem paths,
    and must

    3. carry an identity header pinning the agent to the active project.

    All three together are what kept the agent from saying
    `/Users/...obsidian/mind-palace`, listing `taxes` etc.
    """
    project = init_project(tmp_path / "obsidian" / "mindpalace", name="mind-palace")
    token = set_active_project(project)
    try:
        # AGENTS.md with an absolute path the agent would otherwise parrot.
        absolute_root = str(project.root.resolve())
        (project.root / "AGENTS.md").write_text(
            f"# mind-palace\n\nRooted at {absolute_root}.\n", encoding="utf-8"
        )
        store = SessionStore(project.memory_db_path)
        captured = _install_factory_stubs(monkeypatch)

        # Force the proposer to return non-empty proposals — if the
        # daemon path didn't honor include_proposals=False, this string
        # would be in the system prompt.
        from veles.core import subproject_proposer as proposer_mod

        monkeypatch.setattr(
            proposer_mod,
            "recent_proposals",
            lambda _project: [
                {
                    "name": "taxes",
                    "summary": "OTHER_SUBPROJECT_LEAK_MARKER",
                }
            ],
        )

        factory = _make_agent_factory(_build_args(), project=project, store=store)
        factory(None, prompt="опиши текущий проект")

        sp = captured.get("system_prompt") or ""
        # #6 — identity header present and names the project.
        assert "assistant for the `mind-palace` project" in sp
        # #5 — absolute project root is sanitized.
        assert absolute_root not in sp
        assert "<mind-palace>" in sp
        # #3 — other-subproject proposals are NOT injected on daemon path.
        assert "OTHER_SUBPROJECT_LEAK_MARKER" not in sp
    finally:
        reset_active_project(token)


def test_resumed_session_builds_system_prompt(tmp_path: Path, monkeypatch) -> None:
    """M108: build system_prompt on EVERY turn, not just fresh sessions.

    The previous design skipped this on resume to keep recall off the
    hot path — but the Telegram bot keeps reusing the same session for
    follow-up messages, and adapters re-emit the system message at the
    head of every API call. Without this, on the second user message
    the bot lost AGENTS.md context and replied "I don't have access to
    a project" instead of consulting the wiki.
    """
    project = init_project(tmp_path, name="pjresume")
    token = set_active_project(project)
    try:
        (project.root / "AGENTS.md").write_text(
            "# pjresume\nSENTINEL_MARKER_FROM_AGENTS_MD\n", encoding="utf-8"
        )
        store = SessionStore(project.memory_db_path)
        sid = store.create_session()
        captured = _install_factory_stubs(monkeypatch)

        factory = _make_agent_factory(_build_args(), project=project, store=store)
        factory(sid, prompt="follow-up")
        sp = captured.get("system_prompt")
        assert isinstance(sp, str) and sp
        assert "SENTINEL_MARKER_FROM_AGENTS_MD" in sp
        assert captured.get("session_id") == sid
    finally:
        reset_active_project(token)
