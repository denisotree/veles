"""M117d: write_file enforces layout-pack writable_zones."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.context import reset_active_project, set_active_project
from veles.core.project import init_project
from veles.core.tools.builtin.write_file import write_file


@pytest.fixture()
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


@pytest.fixture()
def project(isolated_home: Path, tmp_path: Path):
    p = init_project(tmp_path / "proj", name="proj")
    token = set_active_project(p)
    yield p
    reset_active_project(token)


# ---- writable paths (default llm-wiki pack) ----


def test_wiki_write_succeeds(project) -> None:
    target = project.root / "wiki" / "concepts" / "x.md"
    msg = write_file(str(target), "hi")
    assert "wrote" in msg
    assert target.read_text(encoding="utf-8") == "hi"


def test_veles_state_write_succeeds(project) -> None:
    """.veles/ is always writable, regardless of pack."""
    target = project.root / ".veles" / "tmp" / "scratch.txt"
    msg = write_file(str(target), "scratch")
    assert "wrote" in msg


def test_agents_md_write_succeeds(project) -> None:
    """AGENTS.md is writable like any other file Veles generates, even
    under llm-wiki whose zones are wiki/ + sources/."""
    target = project.root / "AGENTS.md"
    msg = write_file(str(target), "# AGENTS\n")
    assert "wrote" in msg
    assert target.read_text(encoding="utf-8") == "# AGENTS\n"


# ---- refused paths ----


def test_sources_refused_as_readonly(project) -> None:
    """sources/ is declared readonly in llm-wiki pack."""
    target = project.root / "sources" / "raw.txt"
    msg = write_file(str(target), "x")
    assert "refused" in msg
    assert "writable zones" in msg
    assert not target.exists()


def test_root_level_file_refused(project) -> None:
    """A file at project root outside wiki/ or .veles/ isn't writable
    under llm-wiki."""
    target = project.root / "random.txt"
    msg = write_file(str(target), "x")
    assert "refused" in msg
    assert not target.exists()


def test_refusal_message_lists_allowed_zones(project) -> None:
    target = project.root / "anywhere.txt"
    msg = write_file(str(target), "x")
    # The error message should help the agent: show what IS allowed
    assert ".veles" in msg or "wiki" in msg


# ---- permissive fallback ----


def test_unknown_layout_falls_back_to_permissive(isolated_home: Path, tmp_path: Path) -> None:
    """When the layout-pack doesn't resolve, fall back to permissive
    (any path inside the project root is writable). Preserves the
    pre-M117 contract for projects on custom layouts."""
    from veles.core.project import load_project

    project = init_project(tmp_path / "proj2", name="proj2")
    toml_path = project.project_toml_path
    text = toml_path.read_text(encoding="utf-8")
    toml_path.write_text(
        text.replace('layout = "llm-wiki"', 'layout = "ghost-pack"'),
        encoding="utf-8",
    )
    reloaded = load_project(project.root)

    token = set_active_project(reloaded)
    try:
        target = reloaded.root / "anything.txt"
        msg = write_file(str(target), "ok")
    finally:
        reset_active_project(token)
    assert "wrote" in msg
