"""Veles LLM-wiki content engine — the Karpathy LLM-Wiki pattern as a module.

Extracted from `core/` (2026-06-19): the wiki is ONE optional content pattern,
not a core principle (VISION §4/§5.2). It's active only when a layout pack
enables `[layout.engines] wiki = true` (`core.layout.engines.wiki_enabled`).

Submodules:
- `wiki`   — the `Wiki` store (write/read/search, INDEX/LOG, FTS reindex).
- `tools`  — the `wiki_*` agent tools (registered when the engine is active).
- `linter` — wiki lint (orphans / stale / duplicates) used by dream.
- `ingest` — ingest system prompt + user-message template.
"""

from veles.modules.wiki.ingest import INGEST_SYSTEM_PROMPT, ingest_user_message
from veles.modules.wiki.wiki import Wiki, WikiPageInfo

__all__ = ["INGEST_SYSTEM_PROMPT", "Wiki", "WikiPageInfo", "ingest_user_message"]
