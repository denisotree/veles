"""M164 — end-to-end proof of layout modularity: the `bare` and `notes`
builtin packs run the full memory/learning surface with zero (or
minimal) user-content structure.

Covers per the M160–M163 contract: init scaffolds only what the pack
declares; insight extraction → SQL + `.veles/memory/insights/`; recall
works without wiki; jobs → `.veles/jobs/`; dreaming runs; proposals →
`.veles/memory/proposals/`; `veles add` errors cleanly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from veles.core.layout import clear_engine_cache, find_layout, wiki_enabled
from veles.core.project import Project, init_project
from veles.core.provider import Message, ProviderResponse, TokenUsage


@pytest.fixture(autouse=True)
def _fresh_engine_cache():
    clear_engine_cache()
    yield
    clear_engine_cache()


@pytest.fixture()
def bare_project(tmp_path: Path) -> Project:
    return init_project(tmp_path / "code-repo", name="code-repo", layout="bare")


# ---- init scaffold ----


def test_bare_init_creates_no_content_dirs(bare_project: Project) -> None:
    root = bare_project.root
    assert not (root / "wiki").exists()
    assert not (root / "sources").exists()
    assert not (root / "INDEX.md").exists()
    assert (root / "AGENTS.md").is_file()
    assert (root / ".veles" / "project.toml").is_file()
    assert bare_project.layout_name == "bare"
    assert not wiki_enabled(bare_project)


def test_bare_pack_is_builtin(bare_project: Project) -> None:
    pack = find_layout("bare", project=None)
    assert pack is not None
    assert pack.scope == "builtin"
    assert pack.manifest.writable_zones == ()
    assert pack.manifest.engines == ()


def test_notes_init_scaffolds_notes_dir(tmp_path: Path) -> None:
    project = init_project(tmp_path / "n", name="n", layout="notes")
    assert (project.root / "notes").is_dir()
    assert not (project.root / "wiki").exists()
    agents = (project.root / "AGENTS.md").read_text(encoding="utf-8")
    assert agents.startswith("# n\n")
    assert "notes/" in agents
    assert not wiki_enabled(project)


def test_bare_layout_writes_are_permissive(bare_project: Project) -> None:
    """No declared zones → pre-M117 permissive contract inside the root."""
    from veles.core.layout import is_writable

    assert is_writable(bare_project, bare_project.root / "src" / "main.py")


# ---- insight extraction ----


@dataclass
class _ScriptedProvider:
    name: str = "stub"
    supports_tools: bool = False
    responses: list[ProviderResponse] = field(default_factory=list)
    _idx: int = 0

    def create_message(self, messages, tools=None, *, model: str, max_tokens: int = 4096):
        resp = self.responses[self._idx]
        self._idx += 1
        return resp


def _resp(text: str) -> ProviderResponse:
    return ProviderResponse(
        text=text,
        tool_calls=[],
        usage=TokenUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
        finish_reason="stop",
    )


def test_bare_insight_extraction_lands_in_memory(bare_project: Project) -> None:
    from veles.core.insight_extractor import make_insight_extractor

    provider = _ScriptedProvider(
        responses=[_resp("pin-deps\n\n# Pin deps\n\nAlways pin dependencies.")]
    )
    extractor = make_insight_extractor(provider=provider, model="m", project=bare_project)
    written = extractor(
        [Message(role="user", content="remember to always pin dependencies")],
        "ses-1",
    )
    assert written == 1
    views = list((bare_project.memory_dir / "insights").glob("*.md"))
    assert len(views) == 1
    assert not (bare_project.root / "wiki").exists()


# ---- recall ----


def test_bare_recall_surfaces_memory(bare_project: Project) -> None:
    from veles.core.memory import SessionStore
    from veles.core.memory.router import MemoryRouter
    from veles.core.tools.builtin.memory_save import save_insight_row

    save_insight_row(
        title="deploy flow",
        body="run terraform apply after migrations",
        category="curated-session",
        project=bare_project,
    )
    store = SessionStore(bare_project.memory_db_path)
    try:
        hits = MemoryRouter(bare_project, store=store).recall("terraform deploy", limit=5)
    finally:
        store.close()
    assert any("terraform" in h.summary for h in hits)


# ---- proposals + dreaming ----


def test_bare_proposals_and_dream(bare_project: Project) -> None:
    from veles.core.dreaming import dream_cycle
    from veles.core.memory.artefacts import write_proposal

    write_proposal(bare_project, slug="split-x", title="Split X", content="body")
    result = dream_cycle(bare_project)
    assert result.lint_findings == 0  # wiki steps skipped
    assert (bare_project.memory_dir / "proposals" / "split-x.md").is_file()
    assert (bare_project.memory_dir / "LOG.md").is_file()


# ---- jobs ----


def test_bare_job_output_root(bare_project: Project) -> None:
    assert bare_project.jobs_dir == bare_project.state_dir / "jobs"


# ---- veles add ----


def test_bare_veles_add_errors_cleanly(bare_project: Project, capsys) -> None:
    import argparse

    from veles.cli.commands.ingest import _run_ingest_cli

    args = argparse.Namespace(provider="openrouter")
    rc = _run_ingest_cli(args, bare_project, source="https://example.com")
    assert rc == 2
    err = capsys.readouterr().err
    assert "wiki content engine" in err
    assert "bare" in err


# ---- system prompt ----


def test_bare_system_prompt_has_no_wiki_blocks(bare_project: Project) -> None:
    from veles.cli._runtime import build_run_system_prompt

    prompt = build_run_system_prompt(bare_project, prompt="what do we know?")
    assert prompt is not None
    assert "Wiki habits" not in prompt
    assert "Knowledge base index" not in prompt


# ---- M174: wiki-as-one-layout consistency (gated leak sites) ----


def test_bare_doctor_wiki_check_is_info_not_warn(bare_project: Project) -> None:
    """`veles doctor` must not nag about missing INDEX.md/LOG.md on a
    layout whose wiki engine is off."""
    from veles.core.doctor import _check_wiki_files

    result = _check_wiki_files(bare_project)
    assert result.status == "info"
    assert "no wiki engine" in result.message


def test_bare_subproject_proposer_is_noop(bare_project: Project) -> None:
    """The continuous-curator subproject proposer clusters wiki pages; on a
    non-wiki layout it must return cleanly without constructing a Wiki."""
    import argparse

    from veles.cli._curator import _maybe_run_subproject_proposer

    args = argparse.Namespace(
        continuous_curator=True,
        no_proposer=False,
        no_curator=False,
        provider="openrouter",
    )
    # Must not raise (detect_clusters would build a Wiki the bare layout lacks).
    _maybe_run_subproject_proposer(args, bare_project)
    assert not (bare_project.root / "wiki").exists()


def test_wiki_slash_not_registered_on_bare(bare_project: Project, tmp_path: Path) -> None:
    """`/wiki` is registered only when the active layout enables the wiki
    engine — so it never shows in completion / `/help` on bare/notes."""
    from veles.cli.repl.slash.builtin import build_default_registry

    bare_reg = build_default_registry(project=bare_project)
    assert "/wiki" not in bare_reg.names()
    assert "/save" in bare_reg.names()  # still present (memory fallback)

    wiki_project = init_project(tmp_path / "w", name="w", layout="llm-wiki")
    wiki_reg = build_default_registry(project=wiki_project)
    assert "/wiki" in wiki_reg.names()


def test_bare_help_omits_wiki(bare_project: Project) -> None:
    from veles.cli.repl.slash.builtin import _help
    from veles.cli.repl.slash.registry import SlashContext
    from veles.core.memory import SessionStore
    from veles.core.session_state import AppState

    state = AppState(session_id=None, provider_name="openrouter", model="m")
    store = SessionStore(bare_project.memory_db_path)
    try:
        ctx = SlashContext(state=state, project=bare_project, store=store)
        out = _help("", ctx)
    finally:
        store.close()
    assert "/wiki" not in out.text
    assert "project memory" in out.text  # /save wording reflects no-wiki


def test_bare_save_slash_falls_back_to_insight(bare_project: Project) -> None:
    """`/save <slug>` on a non-wiki layout keeps the reply as a memory
    insight instead of crashing on the absent wiki/queries/ tree."""
    from veles.cli.repl.slash.builtin import _save
    from veles.cli.repl.slash.registry import SlashContext
    from veles.core.memory import SessionStore
    from veles.core.session_state import AppState

    state = AppState(session_id="ses-x", provider_name="openrouter", model="m")
    state.last_assistant_text = "Terraform applies after migrations run."
    store = SessionStore(bare_project.memory_db_path)
    try:
        ctx = SlashContext(state=state, project=bare_project, store=store)
        result = _save("deploy-notes", ctx)
    finally:
        store.close()
    assert not result.is_error
    assert "insight" in result.text
    assert not (bare_project.root / "wiki").exists()
