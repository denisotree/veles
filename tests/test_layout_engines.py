"""M163 — recall, prompt, and toolbelt are correct under any layout.

With the wiki engine off (layout pack without `[layout.engines] wiki`):
no wiki tools in the agent registry, no INDEX/context-file block in the
system prompt, recall surfaces insights/turns only, dream skips
lint/reindex, self-doc lands in `.veles/memory/`. (With it on — the wiki
module from the registry — those are tested with the module.)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.layout import clear_engine_cache, engine_enabled
from veles.core.project import Project, init_project


@pytest.fixture(autouse=True)
def _fresh_engine_cache():
    clear_engine_cache()
    yield
    clear_engine_cache()


@pytest.fixture()
def user_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    (home / ".veles").mkdir(parents=True)
    monkeypatch.setenv("VELES_USER_HOME", str(home))
    return home / ".veles"


@pytest.fixture()
def nowiki_project(tmp_path: Path, user_home: Path) -> Project:
    """A project whose layout pack does NOT enable the wiki engine."""
    pack_dir = user_home / "layouts" / "plain"
    pack_dir.mkdir(parents=True)
    (pack_dir / "layout.toml").write_text('[layout]\nname = "plain"\n', encoding="utf-8")
    return init_project(tmp_path / "p", name="p", layout="plain")


@pytest.fixture()
def wiki_project(tmp_path: Path, wiki_engine: str) -> Project:
    return init_project(tmp_path / "w", name="w", layout=wiki_engine)


# ---- toolset gating ----


class _StubProvider:
    name = "stub"
    supports_tools = True


def test_wiki_tools_dropped_when_engine_off(nowiki_project: Project) -> None:
    from veles.runtime.registry import RUN_TOOLS, load_skills

    reg = load_skills(nowiki_project, RUN_TOOLS, provider=_StubProvider(), model="m")
    names = set(reg.list_names())
    assert not any(n.startswith("wiki_") for n in names)
    assert "read_file" in names
    assert "memory_save_insight" in names


# ---- system prompt ----


def test_prompt_has_no_wiki_blocks_when_engine_off(nowiki_project: Project) -> None:
    from veles.runtime.prompt import build_run_system_prompt

    prompt = build_run_system_prompt(nowiki_project, prompt="anything")
    assert prompt is not None
    assert "Knowledge base index" not in prompt
    assert "Wiki habits" not in prompt


def test_workspace_block_absent_when_engine_off(nowiki_project: Project) -> None:
    from veles.runtime.prompt import build_run_system_prompt

    (nowiki_project.root / "-- Daily --").mkdir()
    prompt = build_run_system_prompt(nowiki_project, prompt="anything")
    assert prompt is not None
    assert "<workspace>" not in prompt  # wiki-layout only


# ---- recall ----


def test_recall_works_without_wiki(nowiki_project: Project) -> None:
    from veles.core.memory import SessionStore
    from veles.core.memory.router import MemoryRouter
    from veles.core.tools.builtin.memory_save import save_insight_row

    rid = save_insight_row(
        title="nginx ratelimit",
        body="bump worker_connections to 4096",
        category="recovery",
        project=nowiki_project,
    )
    assert rid > 0
    store = SessionStore(nowiki_project.memory_db_path)
    try:
        hits = MemoryRouter(nowiki_project, store=store).recall("worker_connections nginx", limit=5)
    finally:
        store.close()
    assert any("worker_connections" in h.summary for h in hits)
    assert all(not h.rel_path.startswith("wiki/") for h in hits)
    # No wiki FTS index appeared as a side effect of recall.
    assert not (nowiki_project.root / "wiki_index.db").exists()


# ---- dream ----


def test_dream_skips_wiki_steps_when_engine_off(nowiki_project: Project) -> None:
    from veles.core.dreaming import dream_cycle

    result = dream_cycle(nowiki_project)
    assert result.lint_findings == 0
    assert result.reindexed_pages == 0
    assert not (nowiki_project.root / "wiki").exists()
    # The dream still journals to the system-ops log.
    assert (nowiki_project.memory_dir / "LOG.md").is_file()


# ---- self-doc ----


def test_self_doc_lands_in_memory_when_engine_off(nowiki_project: Project) -> None:
    from veles.core.self_doc import refresh_self_doc

    rel = refresh_self_doc(nowiki_project)
    assert rel == ".veles/memory/self-doc.md"
    body = (nowiki_project.root / rel).read_text(encoding="utf-8")
    assert "# Self-Documentation" in body
    assert not (nowiki_project.root / "wiki").exists()


# ---- sanity ----


def test_engine_needs_a_contributing_module(wiki_project: Project) -> None:
    """The pack asking for `wiki` is not enough: some module must contribute it."""
    from veles.core.modules import ModuleRegistry, reset_module_registry, set_module_registry

    assert engine_enabled(wiki_project, "wiki")
    token = set_module_registry(ModuleRegistry())  # the stub engine module gone
    try:
        assert not engine_enabled(wiki_project, "wiki")
    finally:
        reset_module_registry(token)


def test_engine_flags(nowiki_project: Project, wiki_project: Project) -> None:
    assert not engine_enabled(nowiki_project, "wiki")
    assert engine_enabled(wiki_project, "wiki")
