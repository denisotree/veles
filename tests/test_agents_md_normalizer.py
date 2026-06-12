"""M96: AGENTS.md merge + apply."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.agents_md_normalizer import (
    ContextFileInfo,
    apply_merge,
    deterministic_merge,
    llm_merge,
    scan_for_context_files,
)
from veles.core.agents_md_schema import validate

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


# ---------------- deterministic merge ----------------


def _info(name: str, content: str) -> ContextFileInfo:
    return ContextFileInfo(
        name=name, path=Path(name), is_symlink=False, size=len(content), content=content
    )


def test_merge_unions_sections() -> None:
    a = _info(
        "AGENTS.md",
        "# Old Project\n\n## Layout\n- src/\n\n## Conventions\n- kebab-case\n",
    )
    b = _info(
        "CLAUDE.md",
        "## Layout\n- tests/\n\n## Workflows\n- run pytest\n",
    )
    merged = deterministic_merge([a, b], project_name="X")
    assert "# Old Project" in merged
    assert "src/" in merged
    assert "tests/" in merged
    assert "kebab-case" in merged
    assert "run pytest" in merged


def test_merge_dedupes_duplicate_lines() -> None:
    a = _info("AGENTS.md", "## Conventions\n- same-rule\n")
    b = _info("CLAUDE.md", "## Conventions\n- same-rule\n- extra\n")
    merged = deterministic_merge([a, b])
    assert merged.count("- same-rule") == 1
    assert "- extra" in merged


def test_merge_fills_missing_recommended_sections() -> None:
    a = _info("AGENTS.md", "# proj\n\n## Conventions\n- rule\n")
    merged = deterministic_merge([a], project_name="proj")
    result = validate(merged)
    # All recommended sections present.
    assert result.ok, f"missing: {result.missing}"


def test_merge_uses_project_name_when_no_h1() -> None:
    a = _info("CLAUDE.md", "## Layout\n- only\n")
    merged = deterministic_merge([a], project_name="my-proj")
    assert merged.startswith("# my-proj")


# ---------------- LLM merge (stubbed) ----------------


class _StubResult:
    def __init__(self, text: str) -> None:
        self.text = text
        self.iterations = 1
        self.history: list = []
        self.session_id = None
        self.stopped_reason = "completed"


class _StubAgent:
    def __init__(self, *_, **__) -> None:
        pass

    def run(self, prompt: str):
        return _StubResult(
            "# Merged\n\n## Layout\n- merged\n\n## Conventions\n- ok\n\n## Workflows\n- run\n"
        )


def test_llm_merge_returns_agent_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("veles.core.agents_md_normalizer.Agent", _StubAgent, raising=False)
    # Patch via runtime — `llm_merge` imports `Agent` inside the function
    # so we shim through `core.agent.Agent` itself.
    monkeypatch.setattr("veles.core.agent.Agent", _StubAgent)
    out = llm_merge(
        provider=object(),
        model="m",
        files=[_info("AGENTS.md", "x")],
        project_name="p",
    )
    assert out.startswith("# Merged")
    assert validate(out).ok


def test_llm_merge_empty_response_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    class _EmptyAgent(_StubAgent):
        def run(self, prompt: str):
            return _StubResult("")

    monkeypatch.setattr("veles.core.agent.Agent", _EmptyAgent)
    with pytest.raises(RuntimeError, match="empty"):
        llm_merge(
            provider=object(),
            model="m",
            files=[_info("AGENTS.md", "x")],
            project_name="p",
        )


# ---------------- apply_merge ----------------


def test_apply_symlink_mode_replaces_originals(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("old", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("claude", encoding="utf-8")
    (tmp_path / "GEMINI.md").write_text("gemini", encoding="utf-8")
    scan = scan_for_context_files(tmp_path)
    actions = apply_merge(tmp_path, "# Merged\n", originals=scan.conflicting, mode="symlink")
    assert (tmp_path / "AGENTS.md").read_text(encoding="utf-8") == "# Merged\n"
    assert (tmp_path / "CLAUDE.md").is_symlink()
    assert (tmp_path / "GEMINI.md").is_symlink()
    assert actions["CLAUDE.md"] == "symlinked to AGENTS.md"


def test_apply_delete_mode_removes_originals(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("a", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("c", encoding="utf-8")
    scan = scan_for_context_files(tmp_path)
    apply_merge(tmp_path, "# Done\n", originals=scan.conflicting, mode="delete")
    assert (tmp_path / "AGENTS.md").exists()
    assert not (tmp_path / "CLAUDE.md").exists()


def test_apply_backup_mode_renames(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("a", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("c", encoding="utf-8")
    scan = scan_for_context_files(tmp_path)
    apply_merge(tmp_path, "# Done\n", originals=scan.conflicting, mode="backup")
    assert (tmp_path / "CLAUDE.md.bak").read_text(encoding="utf-8") == "c"


def test_apply_invalid_mode_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        apply_merge(tmp_path, "x", originals=[], mode="bogus")
