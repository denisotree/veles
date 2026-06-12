"""M76 — dream_cycle orchestrator: each step + state-persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core import dreaming
from veles.core.curator_state import load as load_state
from veles.core.dreaming import dream_cycle
from veles.core.project import Project, init_project


@pytest.fixture()
def project(tmp_path: Path) -> Project:
    return init_project(tmp_path, name="dtest")


def test_dream_no_op_runs_all_cheap_steps(project: Project) -> None:
    result = dream_cycle(project)
    assert not result.skipped


def test_dream_bails_when_project_marker_missing(tmp_path: Path) -> None:
    """M128-followup: if project.toml is gone (project deleted under a running
    daemon), dream_cycle returns early without recreating the state dir."""
    project = init_project(tmp_path / "gone", name="gone")
    import shutil

    shutil.rmtree(project.state_dir)  # simulate a deleted project
    assert not project.state_dir.exists()

    result = dream_cycle(project)
    assert any("project marker" in n for n in result.notes)
    # Crucially, the cycle did NOT mkdir the state dir back into existence.
    assert not project.state_dir.exists()
    assert result.insights_written == 0  # no provider passed
    assert result.dedup_clusters == 0  # no skills installed
    assert result.promote_candidates == 0
    # lint can find e.g. orphans on a fresh wiki, but count is small.
    assert result.lint_findings >= 0


def test_dream_advances_state_cursor(project: Project) -> None:
    before = load_state(project.state_dir / "curator.state.json")
    dream_cycle(project, now=1_700_000_000.0)
    after = load_state(project.state_dir / "curator.state.json")
    assert after.dream_count == before.dream_count + 1
    assert after.last_post_turn_dream_at == 1_700_000_000.0
    assert after.last_deep_dream_at == before.last_deep_dream_at  # not deep


def test_deep_dream_updates_deep_cursor(project: Project) -> None:
    dream_cycle(
        project,
        include_consolidation=True,  # no provider → consolidation step early-returns
        now=1_700_000_000.0,
    )
    after = load_state(project.state_dir / "curator.state.json")
    assert after.last_deep_dream_at == 1_700_000_000.0


def test_dry_run_does_not_persist(project: Project) -> None:
    dream_cycle(project, dry_run=True, now=1234.0)
    after = load_state(project.state_dir / "curator.state.json")
    # dry_run: state file NOT written, default zeros remain.
    assert after.dream_count == 0
    assert after.last_post_turn_dream_at == 0.0


def test_skip_flags_disable_steps(project: Project) -> None:
    result = dream_cycle(
        project,
        skip_insights=True,
        skip_dedup=True,
        skip_promote=True,
        skip_lint=True,
    )
    assert result.dedup_clusters == 0
    assert result.promote_candidates == 0
    assert result.lint_findings == 0


def test_summary_string_is_compact(project: Project) -> None:
    result = dream_cycle(project)
    s = result.summary()
    assert s.startswith("dream:")
    assert "insights=" in s
    assert "lint=" in s


# ---- consolidation step (with a stub provider) ----


def _fixed_text_provider(text: str):
    from tests.conftest import StubProvider
    from veles.core.provider import ProviderResponse, StreamEnd, TextDelta, TokenUsage

    resp = ProviderResponse(
        text=text,
        tool_calls=[],
        usage=TokenUsage(prompt_tokens=1, completion_tokens=2, total_tokens=3),
        finish_reason="stop",
    )
    return StubProvider(
        [resp],
        supports_tools=False,
        supports_streaming=True,
        stream_events=[TextDelta(text=text), StreamEnd(response=resp)],
        repeat_last=True,
    )


def _StubProvider():
    return _fixed_text_provider("## umbrella: foo\n- a\n- b")


def _seed_insights(project: Project, count: int = 3) -> None:
    from veles.core.tools.builtin.memory_save import save_insight_row

    for i in range(count):
        rid = save_insight_row(
            title=f"Insight {i}",
            body=f"Something to remember number {i}.",
            category="test-seed",
            project=project,
        )
        assert rid > 0


def test_consolidate_writes_proposal(project: Project) -> None:
    _seed_insights(project, count=2)
    result = dream_cycle(
        project,
        include_consolidation=True,
        provider=_StubProvider(),
    )
    assert result.consolidated is True
    assert result.consolidation_path is not None
    assert Path(result.consolidation_path).is_file()


def test_consolidate_skips_when_no_insights(project: Project) -> None:
    result = dream_cycle(
        project,
        include_consolidation=True,
        provider=_StubProvider(),
    )
    assert result.consolidated is False
    assert any("no insights" in n for n in result.notes)


def test_consolidate_respects_skip_response(project: Project) -> None:
    _seed_insights(project, count=2)

    result = dream_cycle(
        project,
        include_consolidation=True,
        provider=_fixed_text_provider("SKIP"),
    )
    assert result.consolidated is False
