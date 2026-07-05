"""M190 — llm-wiki migration & log-patch behavioural prompt.

Ties together M188 (`prompt_file` injection) and M189 (permissive llm-wiki):
the builtin `llm-wiki` pack now declares `prompt_file = templates/behaviour.md`,
turning the permissive write model into a migration + log-patch behaviour.

Agentic migration behaviour itself (article -> page, log -> merge/create,
raw -> sources/) is NOT unit-testable — see the release-gate note in
`.superpowers/sdd/m190-report.md`. These tests pin the mechanical surfaces:
the prompt block is present, the pack's prompt file loads, and the tools the
behaviour needs are available in the `run` toolset.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.layout import clear_engine_cache
from veles.core.layout.discovery import find_layout
from veles.core.project import init_project
from veles.core.tools.toolsets import TOOLSETS


@pytest.fixture(autouse=True)
def _fresh_engine_cache():
    clear_engine_cache()
    yield
    clear_engine_cache()


@pytest.fixture()
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


# ---------- prompt injection (ties M188 + M190) ----------


def test_llm_wiki_run_prompt_contains_migration_behaviour(
    isolated_home: Path, tmp_path: Path
) -> None:
    from veles.cli._runtime import build_run_system_prompt

    project = init_project(tmp_path / "proj", name="proj")

    prompt = build_run_system_prompt(project, prompt="migrate this folder into the wiki")

    assert prompt is not None
    assert "Layout behaviour instructions" in prompt
    # Distinctive phrase from templates/behaviour.md — pins that the SHIPPED
    # llm-wiki pack (not a synthetic fixture pack) is the one being loaded.
    assert "semantically weave" in prompt
    assert "log-type record" in prompt


def test_llm_wiki_prompt_declares_migration_and_log_patch_rules(
    isolated_home: Path, tmp_path: Path
) -> None:
    """The prompt must actually encode the three moves the spec calls for:
    raw -> sources/, article -> wiki page, log -> merge-or-create."""
    from veles.cli._runtime import _load_layout_prompt

    project = init_project(tmp_path / "proj", name="proj")

    text = _load_layout_prompt(project)

    assert text is not None
    assert "sources/" in text
    assert "wiki_search" in text
    assert "wiki_write_page" in text
    assert "move_file" in text


# ---------- behaviour.md resolves from the shipped pack ----------


def test_llm_wiki_behaviour_prompt_file_resolves_and_is_non_empty(
    isolated_home: Path, tmp_path: Path
) -> None:
    project = init_project(tmp_path / "proj", name="proj")
    pack = find_layout(project.layout_name, project)

    assert pack is not None
    assert pack.manifest.prompt_file == "templates/behaviour.md"

    path = pack.root / pack.manifest.prompt_file
    assert path.is_file()
    assert len(path.read_text(encoding="utf-8").strip()) > 0


# ---------- tool availability for prompt-driven migration ----------


def test_run_toolset_has_migration_tools() -> None:
    """The `run` toolset (used for prompt-driven migration in a normal
    `veles run`) must expose search/read/write-page and file relocation."""
    run_tools = TOOLSETS["run"]
    # Every tool behaviour.md instructs the agent to use during migration.
    for tool in (
        "wiki_search",
        "wiki_read_page",
        "wiki_write_page",
        "wiki_append_log",
        "move_file",
    ):
        assert tool in run_tools, f"{tool} missing from the `run` toolset"


def test_builtin_toolset_has_wiki_read_surface() -> None:
    """`wiki_search`/`wiki_read_page`/`wiki_list_pages` are read-only and
    already live in `builtin` (which `run` includes)."""
    builtin_tools = TOOLSETS["builtin"]
    for tool in ("wiki_search", "wiki_read_page", "wiki_list_pages"):
        assert tool in builtin_tools
