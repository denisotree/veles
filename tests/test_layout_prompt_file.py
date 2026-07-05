"""M188 — layout-declared behavioural prompt (`prompt_file`).

A layout pack can declare `prompt_file` in `layout.toml`: a `.md` file inside
the PACK root (not the project root) injected into the stable system prompt.
Unlike `context_file` (INDEX.md, wiki-engine-gated), this block is
engine-independent — any pack can use it, wiki or not.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.layout import clear_engine_cache
from veles.core.project import init_project


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


def _make_pack(
    user_home: Path,
    *,
    pack_name: str,
    prompt_file: str | None,
    prompt_body: str | None,
    wiki_engine: bool = False,
) -> None:
    pack_dir = user_home / "layouts" / pack_name
    pack_dir.mkdir(parents=True)
    lines = [f'[layout]\nname = "{pack_name}"\n']
    if prompt_file is not None:
        lines.append(f'prompt_file = "{prompt_file}"\n')
    if wiki_engine:
        lines.append("\n[layout.engines]\nwiki = true\n")
    (pack_dir / "layout.toml").write_text("".join(lines), encoding="utf-8")
    if prompt_file is not None and prompt_body is not None:
        prompt_path = pack_dir / prompt_file
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(prompt_body, encoding="utf-8")


def test_prompt_file_injected_into_stable_prompt(tmp_path: Path, user_home: Path) -> None:
    from veles.cli._runtime import build_run_system_prompt

    _make_pack(
        user_home,
        pack_name="behavioural",
        prompt_file="templates/behaviour.md",
        prompt_body="Always relocate raw sources into sources/ before writing wiki pages.",
    )
    project = init_project(tmp_path / "p", name="p", layout="behavioural")

    prompt = build_run_system_prompt(project, prompt="anything")

    assert prompt is not None
    assert "Layout behaviour" in prompt
    assert "Always relocate raw sources into sources/" in prompt


def test_prompt_file_absent_no_block(tmp_path: Path, user_home: Path) -> None:
    from veles.cli._runtime import build_run_system_prompt

    _make_pack(
        user_home,
        pack_name="no-prompt",
        prompt_file=None,
        prompt_body=None,
    )
    project = init_project(tmp_path / "p", name="p", layout="no-prompt")

    prompt = build_run_system_prompt(project, prompt="anything")

    assert prompt is not None
    assert "Layout behaviour" not in prompt


def test_prompt_file_declared_but_missing_file_no_crash(tmp_path: Path, user_home: Path) -> None:
    from veles.cli._runtime import build_run_system_prompt

    _make_pack(
        user_home,
        pack_name="dangling-prompt",
        prompt_file="templates/behaviour.md",
        prompt_body=None,  # declared but never written
    )
    project = init_project(tmp_path / "p", name="p", layout="dangling-prompt")

    prompt = build_run_system_prompt(project, prompt="anything")

    assert prompt is not None
    assert "Layout behaviour" not in prompt


def test_prompt_file_present_when_wiki_engine_off(tmp_path: Path, user_home: Path) -> None:
    """Engine-independence: the block appears even for a pack that does NOT
    enable the wiki engine — this is a general pack-authoring hook, not a
    wiki feature."""
    from veles.cli._runtime import build_run_system_prompt
    from veles.core.layout import wiki_enabled

    _make_pack(
        user_home,
        pack_name="plain-with-prompt",
        prompt_file="behaviour.md",
        prompt_body="Behave plainly.",
        wiki_engine=False,
    )
    project = init_project(tmp_path / "p", name="p", layout="plain-with-prompt")
    assert not wiki_enabled(project)

    prompt = build_run_system_prompt(project, prompt="anything")

    assert prompt is not None
    assert "Layout behaviour" in prompt
    assert "Behave plainly." in prompt


def test_load_layout_prompt_reads_from_pack_root_not_project_root(
    tmp_path: Path, user_home: Path
) -> None:
    """Critical difference from `context_file`: the prompt file lives in the
    PACK root, so a pack edit reaches existing projects even though the
    project itself never has the file."""
    from veles.cli._runtime import _load_layout_prompt

    _make_pack(
        user_home,
        pack_name="pack-root-prompt",
        prompt_file="templates/behaviour.md",
        prompt_body="Pack-root content, not project-root content.",
    )
    project = init_project(tmp_path / "p", name="p", layout="pack-root-prompt")

    # The project root never gets a copy of the prompt file.
    assert not (project.root / "templates" / "behaviour.md").is_file()

    text = _load_layout_prompt(project)

    assert text is not None
    assert "Pack-root content, not project-root content." in text
