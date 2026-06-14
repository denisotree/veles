"""Tests for veles.core.self_doc — project self-documentation generator."""

from __future__ import annotations

from pathlib import Path

from veles.core.project import init_project
from veles.core.self_doc import (
    SelfDocReport,
    generate_self_doc,
    refresh_self_doc,
    render_self_doc,
)
from veles.core.wiki import Wiki

# ---- helpers ----


def _make_project(tmp_path: Path):
    return init_project(tmp_path / "proj", name="testproject")


def _empty_report(**kwargs) -> SelfDocReport:
    defaults = dict(
        project_name="test",
        created_at="2026-01-01T00:00:00Z",
        session_count=0,
        wiki_page_count=0,
        skills=[],
        tools=[],
        routing={},
        wiki_categories={},
        recent_insights=[],
        log_tail=[],
    )
    defaults.update(kwargs)
    return SelfDocReport(**defaults)


# ---- generate_self_doc ----


def test_generate_self_doc_fresh_project(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    report = generate_self_doc(project)
    assert isinstance(report, SelfDocReport)
    assert report.project_name == "testproject"
    assert report.session_count == 0


def test_generate_self_doc_counts_sessions(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    from veles.core.memory import SessionStore

    with SessionStore(project.memory_db_path) as store:
        store.create_session(title="test session")
    report = generate_self_doc(project)
    assert report.session_count == 1


def test_generate_self_doc_counts_wiki_pages(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    wiki = Wiki(project.wiki_root)
    wiki.write_page(category="concepts", slug="alpha", title="Alpha", content="## Alpha\n\nHello.")
    report = generate_self_doc(project)
    assert report.wiki_page_count == 1


def test_generate_self_doc_lists_skills(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    skill_dir = project.skills_dir / "my-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: my-skill\ndescription: Does things\n---\nBody.\n"
    )
    report = generate_self_doc(project)
    skill_names = [s[0] for s in report.skills]
    assert "my-skill" in skill_names


def test_generate_self_doc_routing_has_default(tmp_path: Path) -> None:
    from veles.core.project_config import save_project_config

    project = _make_project(tmp_path)
    # M165c: routing only resolves with a configured base — give it one so the
    # self-doc routing block has entries.
    save_project_config(project, {"provider": {"default": "ollama", "model": "qwen3:4b"}})
    report = generate_self_doc(project)
    assert "default" in report.routing


def test_generate_self_doc_log_tail_missing_log(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    # LOG.md may be created by init; remove it to test the missing-file branch.
    log_path = project.wiki_root / "LOG.md"
    if log_path.exists():
        log_path.unlink()
    report = generate_self_doc(project)
    assert report.log_tail == []


# ---- render_self_doc ----


def test_render_self_doc_has_required_sections(tmp_path: Path) -> None:
    report = _empty_report()
    md = render_self_doc(report)
    assert "# Self-Documentation" in md
    assert "## Project Status" in md
    assert "## Available Skills" in md
    assert "## Tool Capabilities" in md
    assert "## Routing Configuration" in md
    assert "## Knowledge Summary" in md
    assert "## Recent Insights" in md
    assert "## Activity Log" in md


def test_render_self_doc_empty_skills_message(tmp_path: Path) -> None:
    report = _empty_report(skills=[])
    md = render_self_doc(report)
    assert "_(no skills)_" in md


def test_render_self_doc_with_tools() -> None:
    report = _empty_report(tools=[("read_file", "Read a file"), ("write_file", "Write a file")])
    md = render_self_doc(report)
    assert "`read_file`" in md
    assert "`write_file`" in md
    assert "Read a file" in md


def test_render_self_doc_with_routing() -> None:
    report = _empty_report(routing={"default": "openrouter:anthropic/claude-sonnet-4.6"})
    md = render_self_doc(report)
    assert "`default`" in md
    assert "openrouter" in md


def test_render_self_doc_empty_wiki_message() -> None:
    report = _empty_report(wiki_categories={})
    md = render_self_doc(report)
    assert "_(wiki is empty)_" in md


# ---- refresh_self_doc ----


def test_refresh_self_doc_creates_wiki_page(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    rel = refresh_self_doc(project)
    page_path = project.wiki_root / rel
    assert page_path.is_file()
    assert "# Self-Documentation" in page_path.read_text()


def test_refresh_self_doc_idempotent(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    refresh_self_doc(project)
    refresh_self_doc(project)
    pages = Wiki(project.wiki_root).list_pages()
    self_doc_pages = [p for p in pages if p.category == "self-doc"]
    assert len(self_doc_pages) == 1


def test_refresh_self_doc_logs_op(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    refresh_self_doc(project)
    log_text = (project.memory_dir / "LOG.md").read_text()
    assert "self-doc" in log_text
