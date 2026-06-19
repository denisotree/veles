"""M32 — deterministic wiki linter (orphans, stale, duplicates).

Tests the pure functions in `core/wiki_linter` against a real `Wiki`
on a tmp_path-backed project. INDEX.md is written by `Wiki.write_page`
on every page, so the orphan check works without manual indexing.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

from veles.modules.wiki.linter import (
    _find_oldest_date,
    _title_tokens,
    find_duplicates,
    find_orphans,
    find_stale,
    render_report,
    run_lint,
)
from veles.modules.wiki.wiki import Wiki


def _seed_wiki(tmp_path: Path) -> Wiki:
    w = Wiki(tmp_path / "wiki")
    w.ensure_layout()
    return w


# ---- _title_tokens / _find_oldest_date ----


def test_title_tokens_drops_stopwords_and_short() -> None:
    assert _title_tokens("The Best Page for Karpathy") == {"best", "karpathy"}


def test_find_oldest_date_prefers_iso_over_year() -> None:
    text = "See 2018-03-15 and also 2024."
    out = _find_oldest_date(text)
    assert out is not None
    assert out.year == 2018 and out.month == 3 and out.day == 15


def test_find_oldest_date_falls_back_to_year() -> None:
    out = _find_oldest_date("Era around 2018 only")
    assert out is not None
    assert out.year == 2018


def test_find_oldest_date_returns_none_when_no_date() -> None:
    assert _find_oldest_date("No dates here at all.") is None


def test_find_oldest_date_falls_back_to_year_when_iso_invalid() -> None:
    """An invalid ISO date (2018-13-45) is dropped, but the embedded `2018`
    is still picked up by the year fallback — heuristic, not a strict parse."""
    out = _find_oldest_date("garbage 2018-13-45 valid 2020")
    assert out is not None
    assert out.year == 2018


# ---- find_orphans ----


def test_orphan_detected_when_no_inbound_link(tmp_path: Path) -> None:
    w = _seed_wiki(tmp_path)
    # Write a hub page that does NOT mention the orphan.
    w.write_page(category="concepts", slug="hub", title="Hub", content="No links here.")
    # Replace the auto-generated INDEX.md with one that omits the orphan.
    (w.root / "INDEX.md").write_text("# INDEX\n\n(no pages)\n", encoding="utf-8")
    # Now write the orphan; INDEX.md will be regenerated to include it.
    # Then revert INDEX.md so the orphan really is unreferenced.
    w.write_page(category="concepts", slug="orphan", title="Orphan", content="No backlinks.")
    (w.root / "INDEX.md").write_text("# INDEX\n\n(no pages)\n", encoding="utf-8")

    findings = find_orphans(w)
    rel_paths = [f.pages[0] for f in findings]
    assert "wiki/concepts/orphan.md" in rel_paths
    assert "wiki/concepts/hub.md" in rel_paths


def test_orphan_skipped_when_referenced_from_index(tmp_path: Path) -> None:
    w = _seed_wiki(tmp_path)
    w.write_page(category="concepts", slug="alpha", title="Alpha", content="content")
    # Default INDEX.md (auto-written by write_page) DOES list every page,
    # so alpha is non-orphan even with no other inbound links.
    findings = find_orphans(w)
    assert all("alpha" not in f.pages[0] for f in findings)


def test_orphan_skipped_when_referenced_from_other_page(tmp_path: Path) -> None:
    w = _seed_wiki(tmp_path)
    w.write_page(
        category="concepts",
        slug="target",
        title="Target",
        content="A target page.",
    )
    w.write_page(
        category="concepts",
        slug="hub",
        title="Hub",
        content="Visit [target](wiki/concepts/target.md) for details.",
    )
    # Wipe INDEX so non-orphan status comes ONLY from the hub→target link.
    (w.root / "INDEX.md").write_text("(empty)\n", encoding="utf-8")
    findings = find_orphans(w)
    assert all("target" not in f.pages[0] for f in findings)


def test_orphan_skips_sessions(tmp_path: Path) -> None:
    w = _seed_wiki(tmp_path)
    w.write_page(category="sessions", slug="s1", title="S1", content="x")
    (w.root / "INDEX.md").write_text("(empty)\n", encoding="utf-8")
    findings = find_orphans(w)
    assert findings == []


# ---- find_stale ----


def test_stale_flags_old_iso_date(tmp_path: Path) -> None:
    w = _seed_wiki(tmp_path)
    w.write_page(
        category="concepts",
        slug="old",
        title="Old",
        content="Was true in 2010-01-01.",
    )
    now = _dt.datetime(2026, 1, 1, tzinfo=_dt.UTC)
    findings = find_stale(w, max_age_days=365, now=now)
    assert len(findings) == 1
    assert "old" in findings[0].pages[0]


def test_stale_passes_recent_date(tmp_path: Path) -> None:
    w = _seed_wiki(tmp_path)
    w.write_page(
        category="concepts",
        slug="fresh",
        title="Fresh",
        content="Updated 2025-12-01.",
    )
    now = _dt.datetime(2026, 1, 1, tzinfo=_dt.UTC)
    findings = find_stale(w, max_age_days=365, now=now)
    assert findings == []


def test_stale_skips_dateless_page(tmp_path: Path) -> None:
    w = _seed_wiki(tmp_path)
    w.write_page(category="concepts", slug="abstract", title="Abstract", content="Pure prose.")
    findings = find_stale(w)
    assert findings == []


def test_stale_skips_sessions(tmp_path: Path) -> None:
    w = _seed_wiki(tmp_path)
    w.write_page(category="sessions", slug="s1", title="S1", content="As of 2010-01-01.")
    now = _dt.datetime(2026, 1, 1, tzinfo=_dt.UTC)
    assert find_stale(w, max_age_days=365, now=now) == []


# ---- find_duplicates ----


def test_duplicates_cluster_by_title_token_overlap(tmp_path: Path) -> None:
    w = _seed_wiki(tmp_path)
    w.write_page(
        category="concepts",
        slug="agent-loop-design",
        title="Agent Loop Design",
        content="x",
    )
    w.write_page(
        category="concepts",
        slug="agent-loop-architecture",
        title="Agent Loop Architecture",
        content="y",
    )
    findings = find_duplicates(w, similarity_threshold=0.5)
    assert len(findings) == 1
    assert {p.endswith(".md") for p in findings[0].pages} == {True}
    assert any("agent-loop-design" in p for p in findings[0].pages)
    assert any("agent-loop-architecture" in p for p in findings[0].pages)


def test_duplicates_only_within_same_category(tmp_path: Path) -> None:
    w = _seed_wiki(tmp_path)
    w.write_page(category="concepts", slug="agent", title="Agent", content="x")
    w.write_page(category="entities", slug="agent", title="Agent", content="y")
    findings = find_duplicates(w, similarity_threshold=0.5)
    assert findings == []


def test_duplicates_skips_dissimilar_titles(tmp_path: Path) -> None:
    w = _seed_wiki(tmp_path)
    w.write_page(category="concepts", slug="alpha", title="Alpha Frameworks", content="a")
    w.write_page(category="concepts", slug="bravo", title="Bravo Patterns", content="b")
    findings = find_duplicates(w, similarity_threshold=0.5)
    assert findings == []


def test_duplicates_skips_sessions_and_insights(tmp_path: Path) -> None:
    w = _seed_wiki(tmp_path)
    w.write_page(category="sessions", slug="alpha-loop", title="Alpha Loop", content="a")
    w.write_page(category="sessions", slug="alpha-loop-2", title="Alpha Loop 2", content="b")
    assert find_duplicates(w, similarity_threshold=0.3) == []


# ---- run_lint + render_report ----


def test_run_lint_returns_empty_report_for_fresh_wiki(tmp_path: Path) -> None:
    w = _seed_wiki(tmp_path)
    report = run_lint(w)
    assert report.all_findings == []


def test_render_report_clean_when_no_findings(tmp_path: Path) -> None:
    w = _seed_wiki(tmp_path)
    out = render_report(run_lint(w))
    assert "Veles wiki lint report" in out
    assert "No issues found" in out


def test_render_report_lists_each_kind(tmp_path: Path) -> None:
    w = _seed_wiki(tmp_path)
    # An orphan + a stale + a duplicate cluster.
    w.write_page(
        category="concepts",
        slug="a-old",
        title="Agent Loop A",
        content="As of 2010-01-01.",
    )
    w.write_page(category="concepts", slug="a-new", title="Agent Loop B", content="content")
    (w.root / "INDEX.md").write_text("(empty)\n", encoding="utf-8")
    now = _dt.datetime(2026, 1, 1, tzinfo=_dt.UTC)
    rendered = render_report(run_lint(w, max_age_days=365, now=now), now=now)
    assert "## Orphans" in rendered
    assert "## Stale" in rendered
    assert "## Duplicates" in rendered
