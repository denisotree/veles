"""M249: `[[wiki-link]]` resolution is checked deterministically.

Nothing verified outbound links before: `find_orphans` asks the opposite
question (inbound references) and matches `rel_path` substrings, never parsing
`[[...]]`. So an agent could write 15 pages, log "Cross-link audit passed … all
resolve their [[wiki-link]] targets (NONE unresolved)", have the CHECK advisor
accept the goal on that claim — and be wrong about 102 of 159 links. The fix is
to compute the answer from disk and hand it back in the tool result, where the
model cannot narrate over it.
"""

from __future__ import annotations

from pathlib import Path

from veles.modules.wiki.links import (
    normalize_link,
    parse_links,
    render_link_warning,
    unresolved_links,
)
from veles.modules.wiki.linter import find_broken_links
from veles.modules.wiki.wiki import Wiki

# ---------- parsing ----------


def test_parses_plain_piped_and_anchored_links() -> None:
    text = "see [[alpha]], [[beta|Beta Page]], [[gamma#Section]] and [[delta^block]]"
    assert parse_links(text) == ["alpha", "beta|Beta Page", "gamma#Section", "delta^block"]


def test_normalisation_matches_obsidian_forgiveness() -> None:
    """Case-insensitive, punctuation folded — `[[Speak, Memory]]` must resolve
    to `speak-memory.md`, or a link Obsidian opens would be called broken."""
    assert normalize_link("Speak, Memory") == "speak-memory"
    assert normalize_link("Vladimir Nabokov") == "vladimir-nabokov"
    assert normalize_link("beta|Beta Page") == "beta"
    assert normalize_link("gamma#Section") == "gamma"


def test_the_real_failure_shape_is_reported() -> None:
    """The exact miss from the live run: page named with a slug, linked by title
    — the apostrophe makes them differ even after folding."""
    known = {"nabokov-aesthetic-principles"}
    assert unresolved_links("[[Nabokov's aesthetic principles]]", known) == [
        "Nabokov's aesthetic principles"
    ]
    # And the form the model should have used resolves.
    assert (
        unresolved_links("[[nabokov-aesthetic-principles|Nabokov's aesthetic principles]]", known)
        == []
    )


def test_unresolved_dedupes_and_keeps_order() -> None:
    out = unresolved_links("[[b]] [[a]] [[b]] [[c]]", {"c"})
    assert out == ["b", "a"]


def test_no_links_means_nothing_unresolved() -> None:
    assert unresolved_links("plain prose, no links", {"a"}) == []
    assert render_link_warning([], total=0) == ""


def test_warning_names_the_fix() -> None:
    msg = render_link_warning(["X", "Y"], total=5)
    assert "2 of 5" in msg
    assert "[[slug|Display]]" in msg


def test_warning_truncates_a_long_list() -> None:
    msg = render_link_warning([f"t{i}" for i in range(20)], total=20, limit=3)
    assert "+17 more" in msg


# ---------- wired into the write path ----------


def _wiki(tmp_path: Path) -> Wiki:
    w = Wiki(tmp_path)
    w.ensure_layout()
    return w


def test_write_page_reports_unresolved_links(tmp_path: Path) -> None:
    from veles.core.context import reset_active_project, set_active_project
    from veles.core.project import init_project
    from veles.modules.wiki.tools import wiki_write_page

    project = init_project(tmp_path / "p", name="p")
    token = set_active_project(project)
    try:
        out = wiki_write_page(
            category="concepts",
            slug="alpha",
            title="Alpha",
            content="# Alpha\n\nSee [[Some Missing Page]].",
        )
    finally:
        reset_active_project(token)

    assert "wrote wiki/concepts/alpha.md" in out
    assert "do not resolve" in out, "the model must be told, in the tool result"
    assert "Some Missing Page" in out


def test_write_page_stays_quiet_when_links_resolve(tmp_path: Path) -> None:
    from veles.core.context import reset_active_project, set_active_project
    from veles.core.project import init_project
    from veles.modules.wiki.tools import wiki_write_page

    project = init_project(tmp_path / "p", name="p")
    token = set_active_project(project)
    try:
        wiki_write_page(category="concepts", slug="beta", title="Beta", content="# Beta\n\nbody")
        out = wiki_write_page(
            category="concepts",
            slug="alpha",
            title="Alpha",
            content="# Alpha\n\nSee [[beta]] and [[beta|Beta]].",
        )
    finally:
        reset_active_project(token)

    assert out == "wrote wiki/concepts/alpha.md"


def test_a_page_may_link_to_itself(tmp_path: Path) -> None:
    """The check runs AFTER the write, so a self-reference resolves."""
    w = _wiki(tmp_path)
    w.write_page(category="concepts", slug="alpha", title="Alpha", content="# Alpha\n\n[[alpha]]")
    unresolved, total = w.check_links("[[alpha]]")
    assert (unresolved, total) == ([], 1)


# ---------- wired into lint ----------


def test_lint_reports_broken_links(tmp_path: Path) -> None:
    w = _wiki(tmp_path)
    w.write_page(category="concepts", slug="alpha", title="Alpha", content="# Alpha\n\n[[ghost]]")
    findings = find_broken_links(w)
    assert len(findings) == 1
    assert findings[0].kind == "broken_link"
    assert "ghost" in findings[0].description


def test_lint_is_clean_when_every_link_resolves(tmp_path: Path) -> None:
    w = _wiki(tmp_path)
    w.write_page(category="concepts", slug="alpha", title="Alpha", content="# Alpha\n\n[[beta]]")
    w.write_page(category="concepts", slug="beta", title="Beta", content="# Beta\n\n[[alpha]]")
    assert find_broken_links(w) == []


def test_run_lint_includes_broken_links(tmp_path: Path) -> None:
    from veles.modules.wiki.linter import render_report, run_lint

    w = _wiki(tmp_path)
    w.write_page(category="concepts", slug="alpha", title="Alpha", content="# Alpha\n\n[[ghost]]")
    report = run_lint(w)
    assert report.broken_links, "broken links must reach the report"
    assert any(f.kind == "broken_link" for f in report.all_findings)
    assert "Broken links" in render_report(report)
