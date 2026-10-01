"""Wiki dream steps — the engine's `dream_step` contributions (moved from
`core/dreaming.py`): lint the wiki into a proposal, refresh a stale FTS index.
Both are no-ops when the layout doesn't enable the engine."""

from __future__ import annotations

from typing import TYPE_CHECKING

from veles.core.layout.engines import wiki_enabled
from veles.core.memory.artefacts import append_memory_log, write_proposal
from veles.core.slug import now_timestamp_slug
from veles.modules.wiki.wiki import Wiki

if TYPE_CHECKING:
    from veles.core.dreaming import DreamResult
    from veles.core.project import Project


def lint_step(project: Project, result: DreamResult, *, dry_run: bool) -> None:
    if not wiki_enabled(project):
        return
    from veles.modules.wiki.linter import render_report, run_lint

    report = run_lint(Wiki(project.wiki_root))
    result.lint_findings = len(report.all_findings)
    if result.lint_findings == 0 or dry_run:
        return
    rendered = render_report(report)
    slug = f"dream-lint-{now_timestamp_slug()}"
    write_proposal(
        project,
        slug=slug,
        title="Dream: wiki lint",
        content=rendered,
    )
    append_memory_log(project, op="dream_lint", summary=f"{result.lint_findings} findings")


def reindex_step(project: Project, result: DreamResult, *, dry_run: bool) -> None:
    """M84: refresh the wiki FTS index when dream notices it's stale.
    Cheap when fresh (mtime check), full rebuild otherwise. Never on a dry run."""
    if dry_run or not wiki_enabled(project):
        return
    result.reindexed_pages = Wiki(project.wiki_root).reindex_if_stale()
