"""M34 — AGENTS.md schema validation.

Pure-function tests on the H2 extractor + recommended-section
checker, plus a roundtrip via `init_project` that confirms the new
default template passes validation out of the box.
"""

from __future__ import annotations

from pathlib import Path

from veles.core.agents_md_schema import (
    RECOMMENDED_SECTIONS,
    default_template,
    extract_h2_sections,
    validate,
)
from veles.core.project import init_project

# ---- extract_h2_sections ----


def test_extract_h2_basic_order_preserved() -> None:
    text = "# Title\n\n## Layout\n\nstuff\n\n## Workflows\n"
    assert extract_h2_sections(text) == ["Layout", "Workflows"]


def test_extract_h2_ignores_h1_and_h3() -> None:
    text = "# H1\n## H2-A\n### H3\n## H2-B\n"
    assert extract_h2_sections(text) == ["H2-A", "H2-B"]


def test_extract_h2_empty_input_returns_empty_list() -> None:
    assert extract_h2_sections("") == []


def test_extract_h2_strips_trailing_whitespace() -> None:
    text = "## Layout   \n\n## Workflows\t\n"
    assert extract_h2_sections(text) == ["Layout", "Workflows"]


# ---- validate ----


def test_validate_complete_template_passes() -> None:
    text = default_template("demo")
    result = validate(text)
    assert result.ok
    assert result.missing == []


def test_validate_partial_reports_missing_sections() -> None:
    text = "# title\n\n## Layout\n"
    result = validate(text)
    assert not result.ok
    assert "Layout" not in result.missing
    assert "Conventions" in result.missing
    assert "Workflows" in result.missing


def test_validate_empty_lists_all_recommended_as_missing() -> None:
    result = validate("")
    assert set(result.missing) == set(RECOMMENDED_SECTIONS)
    assert result.present == []


def test_validate_is_case_insensitive() -> None:
    text = "## layout\n## conventions\n## workflows\n"
    result = validate(text)
    assert result.ok


def test_validate_extra_sections_dont_invalidate() -> None:
    text = "## Layout\n## Conventions\n## Workflows\n## On-demand\n## Loaded files\n"
    result = validate(text)
    assert result.ok
    assert "On-demand" in result.present
    assert "Loaded files" in result.present


# ---- default_template + init_project integration ----


def test_default_template_passes_validation() -> None:
    assert validate(default_template("anything")).ok


def test_default_template_includes_project_name() -> None:
    assert "# my-project\n" in default_template("my-project")


def test_init_project_writes_passing_template(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    assert validate(project.agents_md_path.read_text(encoding="utf-8")).ok
