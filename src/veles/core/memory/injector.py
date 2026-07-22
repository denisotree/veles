"""Format MemoryRouter recall hits into a `<memory-context>` block.

The block is appended to the system prompt at run/query time so the LLM
sees the most relevant prior wiki pages without having to call
wiki_search itself. Tag names match the streaming context-scrubber
convention so the block can be stripped on streaming boundaries when
memory rotates.
"""

from __future__ import annotations

from veles.core.memory.artefacts import ProposalInfo
from veles.core.memory.router import RecallHit

_BLOCK_OPEN = "<memory-context>"
_BLOCK_CLOSE = "</memory-context>"
_PROPOSALS_OPEN = "<subproject-proposals>"
_PROPOSALS_CLOSE = "</subproject-proposals>"
_QUERY_HEADER_CAP = 120
_PROPOSALS_MAX_CHARS = 1500


def build_memory_context_block(
    hits: list[RecallHit], query: str, *, max_chars: int = 4000, _total: int | None = None
) -> str | None:
    if not hits:
        return None
    # M219: `_total` carries the ORIGINAL hit count across the drop-to-fit
    # recursion so the header can announce "showing N of M" — a silently
    # shortened list otherwise reads as "nothing else matched" (graphify's
    # truncation-notice lesson: silence must never read as absence).
    total = len(hits) if _total is None else _total
    header_query = query.strip().replace("\n", " ")[:_QUERY_HEADER_CAP]
    if len(hits) < total:
        header = (
            f'Showing {len(hits)} of {total} matches for "{header_query}" '
            "(truncated to fit context — refine the query for the rest):"
        )
    else:
        header = f'Top {len(hits)} matches for "{header_query}":'
    lines = [_BLOCK_OPEN, header]
    for h in hits:
        summary = h.summary.strip() or "(no summary)"
        lines.append(f"- {h.rel_path} — {h.title}: {summary}")
    lines.append(_BLOCK_CLOSE)
    block = "\n".join(lines)
    if len(block) <= max_chars:
        return block
    if len(hits) > 1:
        return build_memory_context_block(hits[:-1], query, max_chars=max_chars, _total=total)
    suffix = "…(truncated to fit context)\n" + _BLOCK_CLOSE
    cut = max_chars - len(suffix)
    if cut <= 0:
        return _BLOCK_OPEN + "\n" + _BLOCK_CLOSE
    return block[:cut] + suffix


def build_proposals_block(
    proposals: list[ProposalInfo], *, max_chars: int = _PROPOSALS_MAX_CHARS
) -> str | None:
    """Render fresh M62 subproject proposals into a system-prompt block.

    The agent reads this block on every turn after the auto-trigger
    fires, and can choose to surface the suggestions to the user
    (VISION §2.2: the agent — not the user — initiates decomposition).
    """
    if not proposals:
        return None
    lines = [
        _PROPOSALS_OPEN,
        f"The curator has identified {len(proposals)} candidate subproject(s) "
        "in this project. Each is persisted under .veles/memory/proposals/.",
        "Consider mentioning these to the user when relevant:",
    ]
    for p in proposals:
        summary = p.summary.strip() or "(no summary)"
        lines.append(f"- {p.slug}: {summary}")
    lines.append(
        "To accept one: `veles subproject init <slug>` then move the listed "
        "pages into the new subproject's wiki/."
    )
    lines.append(_PROPOSALS_CLOSE)
    block = "\n".join(lines)
    if len(block) <= max_chars:
        return block
    if len(proposals) > 1:
        return build_proposals_block(proposals[:-1], max_chars=max_chars)
    suffix = "...\n" + _PROPOSALS_CLOSE
    cut = max_chars - len(suffix)
    if cut <= 0:
        return _PROPOSALS_OPEN + "\n" + _PROPOSALS_CLOSE
    return block[:cut] + suffix
