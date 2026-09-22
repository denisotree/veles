"""M96 normalizer, wired in M272: bring an existing CLAUDE.md / GEMINI.md into AGENTS.md.

The import has to be *lossless*, and that is not a style preference: the M96
`deterministic_merge` was measured on a realistic CLAUDE.md before being wired,
and it dropped the one rule the file contained (everything before the first
`##`) and removed repeated lines — blank lines and the second code block's
fences — so fenced code spilled into prose. `REALISTIC_CLAUDE_MD` below is that
probe, kept as the regression fixture.
"""

from __future__ import annotations

from pathlib import Path

from veles.core.agents_md_normalizer import (
    ContextFileInfo,
    apply_merge,
    import_context_files,
    scan_for_context_files,
)

REALISTIC_CLAUDE_MD = """# My project

Always answer in French. Never touch the prod/ directory.

## Commands

Run the tests:

```bash
pytest -q
```

Then lint:

```bash
ruff check .
```
"""

# ---------------- scan ----------------


def test_scan_empty_dir_returns_no_files(tmp_path: Path) -> None:
    res = scan_for_context_files(tmp_path)
    assert res.files == []
    assert res.needs_merge is False


def test_scan_recognises_real_files_and_symlinks(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("a", encoding="utf-8")
    (tmp_path / "CLAUDE.md").symlink_to("AGENTS.md")
    (tmp_path / "GEMINI.md").write_text("g", encoding="utf-8")
    res = scan_for_context_files(tmp_path)
    by_name = {f.name: f for f in res.files}
    assert by_name["AGENTS.md"].is_symlink is False
    assert by_name["CLAUDE.md"].is_symlink is True
    assert by_name["GEMINI.md"].is_symlink is False
    assert res.needs_merge is True


def test_scan_does_not_need_merge_with_one_real_file(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("a", encoding="utf-8")
    res = scan_for_context_files(tmp_path)
    assert res.needs_merge is False


# ---------------- import ----------------


def _info(name: str, content: str) -> ContextFileInfo:
    return ContextFileInfo(
        name=name, path=Path(name), is_symlink=False, size=len(content), content=content
    )


def test_a_single_file_is_imported_byte_for_byte() -> None:
    assert import_context_files([_info("CLAUDE.md", REALISTIC_CLAUDE_MD)]) == REALISTIC_CLAUDE_MD


def test_a_second_different_file_is_kept_whole_under_its_own_heading() -> None:
    gemini = "# Gemini notes\n\nPrefer short answers.\n"
    out = import_context_files(
        [_info("CLAUDE.md", REALISTIC_CLAUDE_MD), _info("GEMINI.md", gemini)]
    )
    assert out.startswith(REALISTIC_CLAUDE_MD.rstrip())
    assert "## Imported from GEMINI.md" in out
    assert "Prefer short answers." in out


def test_identical_files_are_not_imported_twice() -> None:
    out = import_context_files(
        [_info("CLAUDE.md", REALISTIC_CLAUDE_MD), _info("GEMINI.md", REALISTIC_CLAUDE_MD)]
    )
    assert out == REALISTIC_CLAUDE_MD


def test_empty_sources_import_nothing() -> None:
    assert import_context_files([_info("CLAUDE.md", "  \n")]) == ""


# ---------------- apply ----------------


def test_apply_writes_agents_md_and_keeps_the_original(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text("c", encoding="utf-8")
    scan = scan_for_context_files(tmp_path)
    actions = apply_merge(tmp_path, "# Done\n", originals=scan.conflicting)
    assert (tmp_path / "AGENTS.md").read_text(encoding="utf-8") == "# Done\n"
    assert (tmp_path / "CLAUDE.md.bak").read_text(encoding="utf-8") == "c"
    assert not (tmp_path / "CLAUDE.md").exists()
    assert actions["CLAUDE.md"] == "kept as CLAUDE.md.bak"


def test_apply_never_overwrites_an_existing_backup(tmp_path: Path) -> None:
    """`Path.rename` replaces an existing target on POSIX; a user's own
    `CLAUDE.md.bak` must survive the import."""
    (tmp_path / "CLAUDE.md").write_text("new", encoding="utf-8")
    (tmp_path / "CLAUDE.md.bak").write_text("the user's older backup", encoding="utf-8")
    scan = scan_for_context_files(tmp_path)
    apply_merge(tmp_path, "# Done\n", originals=scan.conflicting)
    assert (tmp_path / "CLAUDE.md.bak").read_text(encoding="utf-8") == "the user's older backup"
    assert (tmp_path / "CLAUDE.md.bak.1").read_text(encoding="utf-8") == "new"


# ---------------- through `init_project` (the real path) ----------------


def test_init_loads_an_existing_claude_md(tmp_path: Path) -> None:
    """The reported bug, end to end: the agent must *see* the rule — asserted
    through `load_agents_md`, which is what feeds the prompt. Before M272 the
    rule appeared 0 times in AGENTS.md."""
    from veles.core.project import init_project, load_agents_md

    root = tmp_path / "proj"
    root.mkdir()
    (root / "CLAUDE.md").write_text(REALISTIC_CLAUDE_MD, encoding="utf-8")
    project = init_project(root, name="proj", layout="bare")

    loaded = load_agents_md(project) or ""
    assert "Always answer in French" in loaded
    assert loaded.count("```") == 4  # both code blocks intact
    assert (root / "CLAUDE.md").is_symlink()  # Claude CLI now reads the same file
    assert (root / "CLAUDE.md.bak").read_text(encoding="utf-8") == REALISTIC_CLAUDE_MD


def test_init_never_rewrites_an_existing_agents_md(tmp_path: Path) -> None:
    from veles.core.project import init_project

    root = tmp_path / "proj"
    root.mkdir()
    (root / "AGENTS.md").write_text("# Mine\n\nKeep this.\n", encoding="utf-8")
    (root / "CLAUDE.md").write_text("something else", encoding="utf-8")
    init_project(root, name="proj", layout="bare")
    assert (root / "AGENTS.md").read_text(encoding="utf-8") == "# Mine\n\nKeep this.\n"
    assert (root / "CLAUDE.md").read_text(encoding="utf-8") == "something else"  # untouched


def test_init_without_context_files_still_scaffolds(tmp_path: Path) -> None:
    from veles.core.project import init_project

    root = tmp_path / "proj"
    root.mkdir()
    init_project(root, name="proj", layout="bare")
    assert (root / "AGENTS.md").is_file()
    assert not list(root.glob("*.bak"))
