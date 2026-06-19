"""Unit + integration tests for per-turn memory recall.

Covers:
- MemoryRouter (wraps Wiki.search) — recall_* tests.
- build_memory_context_block — injector_* tests.
- _build_run_system_prompt integration — prompt_* tests.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from veles.core.memory.injector import build_memory_context_block
from veles.core.memory.router import MemoryRouter, RecallHit
from veles.core.project import init_project
from veles.modules.wiki.wiki import Wiki


def _seed_wiki(project_root: Path, pages: list[tuple[str, str, str, str]]) -> Wiki:
    # v2: wiki container is the project root, not `.veles/`.
    wiki = Wiki(project_root)
    wiki.ensure_layout()
    for category, slug, title, content in pages:
        wiki.write_page(category=category, slug=slug, title=title, content=content)
    return wiki


# ---------- MemoryRouter ----------


def test_recall_empty_wiki_returns_empty(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    assert MemoryRouter(project).recall("anything") == []


def test_recall_returns_pages_matching_query(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    _seed_wiki(
        project.root,
        [
            (
                "concepts",
                "llm-wiki",
                "LLM Wiki",
                "Karpathy three-layer pattern: sources, wiki, schema.",
            ),
            ("entities", "anthropic", "Anthropic", "AI safety company building Claude."),
            ("concepts", "tokens", "Token Budget", "TokenBudget tracks cumulative LLM cost."),
        ],
    )
    hits = MemoryRouter(project).recall("Karpathy three-layer")
    paths = [h.rel_path for h in hits]
    assert "wiki/concepts/llm-wiki.md" in paths


def test_recall_respects_limit(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    _seed_wiki(
        project.root,
        [
            ("concepts", f"page-{i}", f"Page {i}", f"Repeats keyword karpathy {i} times.")
            for i in range(8)
        ],
    )
    hits = MemoryRouter(project).recall("karpathy", limit=3)
    assert len(hits) <= 3


def test_recall_empty_query_returns_empty(tmp_path: Path) -> None:
    project = init_project(tmp_path, name="t")
    _seed_wiki(project.root, [("concepts", "x", "X", "body")])
    assert MemoryRouter(project).recall("") == []
    assert MemoryRouter(project).recall("   ") == []


# ---------- Injector ----------


def test_injector_returns_none_for_no_hits() -> None:
    assert build_memory_context_block([], "anything") is None


def test_injector_includes_query_in_header() -> None:
    hits = [RecallHit(rel_path="wiki/concepts/x.md", title="X", summary="x")]
    block = build_memory_context_block(hits, "what is x?")
    assert block is not None
    assert '"what is x?"' in block
    assert block.startswith("<memory-context>")
    assert block.rstrip().endswith("</memory-context>")


def test_injector_lists_hits_with_rel_path_title_summary() -> None:
    hits = [
        RecallHit(rel_path="wiki/sessions/abc.md", title="Session A", summary="A summary."),
        RecallHit(rel_path="wiki/concepts/foo.md", title="Foo", summary="Foo summary."),
    ]
    block = build_memory_context_block(hits, "q")
    assert block is not None
    assert "wiki/sessions/abc.md — Session A: A summary." in block
    assert "wiki/concepts/foo.md — Foo: Foo summary." in block


def test_injector_truncates_long_query_in_header() -> None:
    long_query = "x" * 500
    hits = [RecallHit(rel_path="wiki/x.md", title="X", summary="x")]
    block = build_memory_context_block(hits, long_query)
    assert block is not None
    # Header uses 120-char cap.
    quoted = block.splitlines()[1]
    assert len(quoted) <= 200  # "Top 1 matches for \"...\":" with capped query


def test_injector_caps_to_max_chars() -> None:
    big_summary = "x" * 1000
    hits = [
        RecallHit(rel_path=f"wiki/p-{i}.md", title=f"P{i}", summary=big_summary) for i in range(10)
    ]
    block = build_memory_context_block(hits, "q", max_chars=2000)
    assert block is not None
    assert len(block) <= 2000
    # Always closes the block.
    assert block.rstrip().endswith("</memory-context>")


def test_injector_handles_missing_summary() -> None:
    hits = [RecallHit(rel_path="wiki/x.md", title="X", summary="")]
    block = build_memory_context_block(hits, "q")
    assert block is not None
    assert "(no summary)" in block


# ---------- _build_run_system_prompt integration ----------


def _run_args(prompt: str = "test prompt") -> argparse.Namespace:
    return argparse.Namespace(
        prompt=prompt,
        no_agents_md=False,
        no_index=False,
        provider="openrouter",
    )


def test_prompt_includes_memory_context_when_wiki_has_matches(tmp_path: Path) -> None:
    from veles.cli import _build_run_system_prompt

    project = init_project(tmp_path, name="t")
    _seed_wiki(
        project.root,
        [
            ("concepts", "karpathy-wiki", "Karpathy Wiki", "Three-layer LLM Wiki pattern."),
        ],
    )
    args = _run_args(prompt="Karpathy three-layer wiki")
    prompt = _build_run_system_prompt(args, project)
    assert prompt is not None
    assert "<memory-context>" in prompt
    assert "wiki/concepts/karpathy-wiki.md" in prompt


def test_prompt_no_memory_context_when_wiki_empty(tmp_path: Path) -> None:
    from veles.cli import _build_run_system_prompt

    project = init_project(tmp_path, name="t")
    args = _run_args(prompt="anything")
    prompt = _build_run_system_prompt(args, project)
    # Empty wiki → no recall block. AGENTS.md is auto-generated by init_project,
    # so prompt may be non-None, but it must not contain memory-context.
    if prompt is not None:
        assert "<memory-context>" not in prompt


def test_prompt_skips_recall_with_empty_prompt(tmp_path: Path) -> None:
    from veles.cli import _build_run_system_prompt

    project = init_project(tmp_path, name="t")
    _seed_wiki(project.root, [("concepts", "x", "X", "body keyword")])
    args = _run_args(prompt="")
    prompt = _build_run_system_prompt(args, project)
    if prompt is not None:
        assert "<memory-context>" not in prompt
