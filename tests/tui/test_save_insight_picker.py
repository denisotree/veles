"""M87: `/save` lists pending candidates when bare; `/save <slug>` writes
the matching candidate to wiki/insights/ and pops it from state."""

from __future__ import annotations

from veles.core.wiki import Wiki
from veles.tui.slash import build_default_registry
from veles.tui.widgets.status_bar import StatusBar


def _reg():
    return build_default_registry()


def test_bare_save_with_no_candidates_errors(slash_ctx):
    res = _reg().dispatch("/save", slash_ctx)
    assert res is not None and res.is_error


def test_bare_save_lists_candidates(slash_ctx):
    slash_ctx.state.insight_candidates = [
        ("alpha", "Alpha", "body a"),
        ("beta", "Beta", "body b"),
    ]
    res = _reg().dispatch("/save", slash_ctx)
    assert res is not None and not res.is_error
    assert "alpha" in res.text
    assert "beta" in res.text


def test_save_commits_candidate_and_removes_from_list(slash_ctx):
    slash_ctx.state.insight_candidates = [
        ("alpha-note", "Alpha note", "First insight body.")
    ]
    res = _reg().dispatch("/save alpha-note", slash_ctx)
    assert res is not None and not res.is_error
    assert "wiki/insights/alpha-note.md" in res.text
    wiki = Wiki(slash_ctx.project.wiki_root)
    body = wiki.read_page("wiki/insights/alpha-note.md")
    assert "First insight body." in body
    # The committed candidate is popped from state.
    assert slash_ctx.state.insight_candidates == []


def test_unknown_slug_falls_back_to_legacy_queries_save(slash_ctx):
    slash_ctx.state.last_assistant_text = "## Reply\n\nlegacy behaviour"
    slash_ctx.state.insight_candidates = [
        ("alpha-note", "Alpha note", "First insight.")
    ]
    res = _reg().dispatch("/save free-slug", slash_ctx)
    # Falls through to the legacy /save path → writes wiki/queries/.
    assert res is not None and not res.is_error
    assert "wiki/queries/free-slug.md" in res.text
    # The unrelated candidate stays in place.
    assert slash_ctx.state.insight_candidates == [
        ("alpha-note", "Alpha note", "First insight.")
    ]


def test_status_bar_shows_insight_badge():
    from veles.tui.state import AppState

    bar = StatusBar()
    state = AppState(session_id=None, provider_name="openrouter", model="m")
    state.insight_candidates = [("a", "A", "b1"), ("b", "B", "b2")]
    bar.render_state(state)
    assert "2 insight" in bar.last_text
