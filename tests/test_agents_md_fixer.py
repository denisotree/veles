"""Tests for veles.core.agents_md_fixer — LLM-driven AGENTS.md fix wizard."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from veles.core.agents_md_fixer import (
    _append_section,
    _default_section_content,
    _parse_questions,
    fix_agents_md,
    generate_section_content,
    generate_section_questions,
)
from veles.core.agents_md_schema import RECOMMENDED_SECTIONS, default_template

# ---- fixtures ----


@pytest.fixture()
def agents_md(tmp_path: Path) -> Path:
    """A minimal AGENTS.md that is missing all recommended sections."""
    p = tmp_path / "AGENTS.md"
    p.write_text("# myproject\n\nSome content.\n")
    return p


@pytest.fixture()
def valid_agents_md(tmp_path: Path) -> Path:
    """A complete AGENTS.md that passes validate()."""
    p = tmp_path / "AGENTS.md"
    p.write_text(default_template("myproject"))
    return p


# ---- _parse_questions ----


def test_parse_questions_valid_json() -> None:
    raw = json.dumps({"questions": [{"text": "What is X?", "choices": ["A", "B"]}]})
    qs = _parse_questions(raw)
    assert len(qs) == 1
    assert qs[0].text == "What is X?"
    assert qs[0].choices == ["A", "B"]


def test_parse_questions_fenced_json() -> None:
    raw = '```json\n{"questions": [{"text": "Q?", "choices": []}]}\n```'
    qs = _parse_questions(raw)
    assert len(qs) == 1
    assert qs[0].text == "Q?"
    assert qs[0].choices == []


def test_parse_questions_garbage_returns_empty() -> None:
    assert _parse_questions("not json at all") == []


def test_parse_questions_missing_questions_key() -> None:
    assert _parse_questions('{"other": []}') == []


def test_parse_questions_bad_item_skipped() -> None:
    raw = json.dumps(
        {
            "questions": [
                {"text": "", "choices": []},
                {"text": "Good?", "choices": ["A"]},
            ]
        }
    )
    qs = _parse_questions(raw)
    assert len(qs) == 1
    assert qs[0].text == "Good?"


# ---- _default_section_content ----


def test_default_section_content_known_sections() -> None:
    for section in RECOMMENDED_SECTIONS:
        content = _default_section_content(section)
        assert f"## {section}" in content


def test_default_section_content_unknown() -> None:
    content = _default_section_content("Quirks")
    assert "## Quirks" in content


# ---- _append_section ----


def test_append_section_adds_to_file(tmp_path: Path) -> None:
    p = tmp_path / "AGENTS.md"
    p.write_text("# proj\n")
    _append_section(p, "## Layout\n\n- foo\n")
    text = p.read_text()
    assert "## Layout" in text
    assert "# proj" in text


def test_append_section_multiple_calls(tmp_path: Path) -> None:
    p = tmp_path / "AGENTS.md"
    p.write_text("# proj\n")
    _append_section(p, "## Layout\n\n- foo\n")
    _append_section(p, "## Workflows\n\n- bar\n")
    text = p.read_text()
    assert "## Layout" in text
    assert "## Workflows" in text


# ---- generate_section_questions ----


def test_generate_section_questions_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = json.dumps({"questions": [{"text": "Describe layout?", "choices": ["wiki", "flat"]}]})
    monkeypatch.setattr(
        "veles.core.agents_md_fixer._run_sub_agent",
        lambda *a, **kw: raw,
    )
    qs = generate_section_questions("Layout", "myproj", provider="openrouter", model="haiku")
    assert len(qs) == 1
    assert qs[0].text == "Describe layout?"


def test_generate_section_questions_empty_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "veles.core.agents_md_fixer._run_sub_agent",
        lambda *a, **kw: "",
    )
    qs = generate_section_questions("Layout", "myproj", provider="openrouter", model="haiku")
    assert qs == []


def test_generate_section_questions_bad_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "veles.core.agents_md_fixer._run_sub_agent",
        lambda *a, **kw: "garbage response",
    )
    qs = generate_section_questions("Layout", "myproj", provider="openrouter", model="haiku")
    assert qs == []


# ---- generate_section_content ----


def test_generate_section_content_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "veles.core.agents_md_fixer._run_sub_agent",
        lambda *a, **kw: "## Layout\n\n- sources/ raw files\n",
    )
    result = generate_section_content(
        "Layout", "myproj", {"q": "a"}, provider="openrouter", model="haiku"
    )
    assert "## Layout" in result


def test_generate_section_content_fallback_on_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "veles.core.agents_md_fixer._run_sub_agent",
        lambda *a, **kw: "",
    )
    result = generate_section_content(
        "Conventions", "myproj", {}, provider="openrouter", model="haiku"
    )
    assert "## Conventions" in result


def test_generate_section_content_adds_heading_if_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "veles.core.agents_md_fixer._run_sub_agent",
        lambda *a, **kw: "- foo\n- bar\n",  # no heading
    )
    result = generate_section_content(
        "Workflows", "myproj", {}, provider="openrouter", model="haiku"
    )
    assert "## Workflows" in result


# ---- fix_agents_md ----


def test_fix_agents_md_no_op_when_valid(
    valid_agents_md: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "veles.core.agents_md_fixer._run_sub_agent",
        lambda *a, **kw: "",
    )
    added = fix_agents_md(
        valid_agents_md,
        "myproject",
        provider="openrouter",
        model="haiku",
        ask_question=lambda q: "answer",
    )
    assert added == []


def test_fix_agents_md_adds_missing_sections(
    agents_md: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "veles.core.agents_md_fixer._run_sub_agent",
        lambda *a, **kw: "",
    )
    added = fix_agents_md(
        agents_md,
        "myproject",
        provider="openrouter",
        model="haiku",
        ask_question=lambda q: "my answer",
    )
    assert set(added) == set(RECOMMENDED_SECTIONS)


def test_fix_agents_md_appends_to_file(agents_md: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "veles.core.agents_md_fixer._run_sub_agent",
        lambda *a, **kw: "",
    )
    fix_agents_md(
        agents_md,
        "myproject",
        provider="openrouter",
        model="haiku",
        ask_question=lambda q: "",
    )
    text = agents_md.read_text()
    assert "## Workflows" in text
    assert "## Layout" in text
    assert "## Conventions" in text


def test_fix_agents_md_calls_callbacks(agents_md: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    started: list[str] = []
    done: list[str] = []
    monkeypatch.setattr(
        "veles.core.agents_md_fixer._run_sub_agent",
        lambda *a, **kw: "",
    )
    fix_agents_md(
        agents_md,
        "myproject",
        provider="openrouter",
        model="haiku",
        ask_question=lambda q: "",
        on_section_start=started.append,
        on_section_done=done.append,
    )
    assert len(started) == len(RECOMMENDED_SECTIONS)
    assert len(done) == len(RECOMMENDED_SECTIONS)
    assert set(started) == set(RECOMMENDED_SECTIONS)


def test_fix_agents_md_uses_default_on_empty_llm_response(
    agents_md: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the LLM returns empty text, _default_section_content is used."""
    monkeypatch.setattr(
        "veles.core.agents_md_fixer._run_sub_agent",
        lambda *a, **kw: "",
    )
    fix_agents_md(
        agents_md,
        "myproject",
        provider="openrouter",
        model="haiku",
        ask_question=lambda q: "",
    )
    text = agents_md.read_text()
    assert "## Layout" in text


def test_fix_agents_md_missing_file_returns_empty(tmp_path: Path) -> None:
    """Missing AGENTS.md path → return [] immediately."""
    added = fix_agents_md(
        tmp_path / "nonexistent.md",
        "myproject",
        provider="openrouter",
        model="haiku",
        ask_question=lambda q: "answer",
    )
    assert added == []
