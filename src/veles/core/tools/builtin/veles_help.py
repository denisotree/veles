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
    # M325: one shared title/topic word is enough here. The two-word gate exists
    # for recall, where every coding prompt is searched and must not pull Veles
    # docs in; a call to this tool is a question about Veles by definition. With
    # two, a one-word name (`tool_authoring`, `init`) could never be found, and
    # nor could anything asked about in only one Veles word.
    hits = get_default_store().search(query, limit=limit, min_matches=1)
    if not hits:
        return "(no matching Veles documentation — rephrase, or check `veles --help`)"
    blocks: list[str] = []
    for h in hits:
        body = h.body.strip() or "(no detail)"
        blocks.append(f"## {h.title}\n\n{body}")
    return "\n\n".join(blocks)
