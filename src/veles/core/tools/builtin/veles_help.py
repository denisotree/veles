"""`veles_help` tool (M186): deep lookup into Veles self-knowledge.

The recall surface injects short digests automatically; this tool is the
deep-dive path — the agent calls it when it needs the full note text for a
how-to question. Same `KnowledgeStore` as recall: one source, two surfaces.
"""

from __future__ import annotations

from veles.core.risk import RiskClass
from veles.core.tools.registry import tool


@tool(risk_class=RiskClass.SEARCH_ONLY, side_effects=[])
def veles_help(query: str, limit: int = 3) -> str:
    """Answer "how do I do X in Veles" from Veles' own documentation.

    Returns the most relevant curated how-to notes plus live command/skill/tool
    facts. Use this whenever the user asks how to use a Veles feature and the
    recalled `<memory-context>` digest is not enough. `limit` caps the number of
    entries (default 3, max 8).
    """
    from veles.core.knowledge.store import get_default_store

    limit = max(1, min(limit, 8))
    hits = get_default_store().search(query, limit=limit)
    if not hits:
        return "(no matching Veles documentation — rephrase, or check `veles --help`)"
    blocks: list[str] = []
    for h in hits:
        body = h.body.strip() or "(no detail)"
        blocks.append(f"## {h.title}\n\n{body}")
    return "\n\n".join(blocks)
