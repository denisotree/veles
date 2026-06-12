"""M87: batch-mode insight extractor returns parsed candidates without
auto-persisting. The TUI surfaces them via the status-bar badge and
`/save` picker."""

from __future__ import annotations

from veles.core.insight_extractor import InsightCandidate, _parse_batch_output


def test_parses_single_block() -> None:
    raw = (
        "slug: graph-traversal-notes\n"
        "title: Graph traversal notes\n"
        "body:\n"
        "Iterative DFS beats recursive one on deep trees because of stack limits.\n"
    )
    cands = _parse_batch_output(raw)
    assert len(cands) == 1
    assert cands[0] == InsightCandidate(
        slug="graph-traversal-notes",
        title="Graph traversal notes",
        body="Iterative DFS beats recursive one on deep trees because of stack limits.",
    )


def test_parses_multiple_blocks() -> None:
    raw = (
        "slug: a-one\n"
        "title: A One\n"
        "body:\n"
        "first body line\n"
        "\n"
        "slug: b-two\n"
        "title: B Two\n"
        "body:\n"
        "second body line\n"
        "with another\n"
    )
    cands = _parse_batch_output(raw)
    assert [c.slug for c in cands] == ["a-one", "b-two"]
    assert cands[1].body == "second body line\nwith another"


def test_none_returns_empty() -> None:
    assert _parse_batch_output("NONE") == []
    assert _parse_batch_output("") == []
    assert _parse_batch_output("   ") == []


def test_handles_missing_fields() -> None:
    # Block missing the body section is dropped; the second valid block stays.
    raw = "slug: incomplete\ntitle: Incomplete\n\nslug: good\ntitle: Good\nbody:\nok body\n"
    cands = _parse_batch_output(raw)
    assert [c.slug for c in cands] == ["good"]
