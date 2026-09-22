"""Format MemoryRouter recall hits into a `<memory-context>` block.

The block is appended to the system prompt at run/query time so the LLM
sees the most relevant prior wiki pages without having to call
wiki_search itself. Tag names match the streaming context-scrubber
convention so the block can be stripped on streaming boundaries when
memory rotates.
"""

from __future__ import annotations

import re

from veles.core.memory.artefacts import PROMOTE_PROPOSAL_PREFIX, ProposalInfo
from veles.core.memory.router import RecallHit

_BLOCK_OPEN = "<memory-context>"
_BLOCK_CLOSE = "</memory-context>"
# M275: renamed from <subproject-proposals> — the block now also carries skill
# promotions, and a tag that names only one kind is how the two got conflated.
_PROPOSALS_OPEN = "<proposals>"
_PROPOSALS_CLOSE = "</proposals>"
_QUERY_HEADER_CAP = 120
_PROPOSALS_MAX_CHARS = 1500

# M259: the delimiters below are OURS, and everything between them is recalled
# text — insight bodies, page titles, proposal summaries — i.e. content the
# agent itself wrote earlier, or ingested from a source. A stored fact that
# happens to contain `</memory-context>` closes the block early, and the rest
# of recall is then read as ordinary prompt text outside any boundary.
#
# `scan_for_injection` does not cover this: it neutralises `<system>` /
# `<im_start>`, not Veles' own block tags. Escaping (rather than scrubbing) is
# deliberate — a page legitimately documenting these tags stays readable.
_BLOCK_TAG = re.compile(r"<\s*/?\s*(?:memory-context|proposals)\b[^>]*>", re.IGNORECASE)


def _escape_block_tags(text: str) -> str:
    """Neutralise our own block delimiters inside interpolated content."""
    return _BLOCK_TAG.sub(lambda m: m.group(0).replace("<", "&lt;").replace(">", "&gt;"), text)


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
    header_query = _escape_block_tags(query.strip().replace("\n", " ")[:_QUERY_HEADER_CAP])
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
        lines.append(_escape_block_tags(f"- {h.rel_path} — {h.title}: {summary}"))
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
    subprojects: list[ProposalInfo],
    promotions: list[ProposalInfo] | None = None,
    *,
    max_chars: int = _PROPOSALS_MAX_CHARS,
) -> str | None:
    """Render fresh curator proposals into one system-prompt block.

    Two kinds, each with its own accept command, because the command is what
    the agent will relay to the user: M62 subproject clusters (VISION §2.2 —
    the agent, not the user, initiates decomposition) and M61 skill promotions.
    Before M275 a promotion was listed as a "candidate subproject" under
    `veles subproject init <slug>`, which would have created a subproject named
    `promote-<skill>` instead of promoting the skill.
    """
    promotions = promotions or []
    if not subprojects and not promotions:
        return None
    lines = [
        _PROPOSALS_OPEN,
        "The curator left suggestions under .veles/memory/proposals/. "
        "Consider mentioning them to the user when relevant.",
    ]
    if subprojects:
        lines.append(f"Candidate subprojects ({len(subprojects)}):")
        for p in subprojects:
            summary = p.summary.strip() or "(no summary)"
            lines.append(_escape_block_tags(f"- {p.slug}: {summary}"))
        lines.append(
            "To accept one: `veles subproject init <slug>` then move the listed "
            "pages into the new subproject's wiki/."
        )
    if promotions:
        lines.append(f"Skills worth promoting to user scope ({len(promotions)}):")
        for p in promotions:
            name = p.slug.removeprefix(PROMOTE_PROPOSAL_PREFIX)
            summary = p.summary.strip() or "(no summary)"
            lines.append(_escape_block_tags(f"- {name}: {summary}"))
        lines.append(
            "To accept one: `veles skill promote <name>` — the skill then works "
            "in every project on this machine."
        )
    lines.append(_PROPOSALS_CLOSE)
    block = "\n".join(lines)
    if len(block) <= max_chars:
        return block
    # Drop from the tail to fit, promotions first, keeping at least one entry.
    if len(promotions) + len(subprojects) > 1:
        if promotions:
            return build_proposals_block(subprojects, promotions[:-1], max_chars=max_chars)
        return build_proposals_block(subprojects[:-1], max_chars=max_chars)
    suffix = "...\n" + _PROPOSALS_CLOSE
    cut = max_chars - len(suffix)
    if cut <= 0:
        return _PROPOSALS_OPEN + "\n" + _PROPOSALS_CLOSE
    return block[:cut] + suffix
