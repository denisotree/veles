"""Veles LLM-wiki content engine — the Karpathy LLM-Wiki pattern as a module.

Extracted from `core/` (2026-06-19): the wiki is ONE optional content pattern,
not a core principle (VISION §4/§5.2). It's active only when a layout pack
enables `[layout.engines] wiki = true` (`core.layout.engines.wiki_enabled`).

Submodules:
- `wiki`   — the `Wiki` store (write/read/search, INDEX/LOG, FTS reindex).
- `tools`  — the `wiki_*` agent tools (registered when the engine is active).
- `linter` — wiki lint (orphans / stale / duplicates) used by dream.
- `ingest` — ingest user-message template (system prompt is the run prompt, M203).
"""

from veles.modules.wiki.ingest import ingest_user_message
from veles.modules.wiki.wiki import Wiki, WikiPageInfo


def register(api) -> None:
    """Everything the wiki engine adds to Veles, as contributions (release A)."""
    import importlib

    from veles.core.contributions import (
        BackgroundOp,
        CuratorTarget,
        DreamStep,
        Engine,
        PageSource,
        ToolSet,
    )
    from veles.modules.wiki import curator
    from veles.modules.wiki.background import run_ingest_job
    from veles.modules.wiki.dream import lint_step, reindex_step
    from veles.modules.wiki.prompt import wiki_prompt
    from veles.modules.wiki.recall import wiki_recall

    api.contribute("engine", "wiki", Engine("wiki"))
    api.contribute(
        "tool",
        "wiki",
        ToolSet(
            load=lambda: importlib.import_module("veles.modules.wiki.tools"),
            tools=WIKI_TOOLS,
            engine="wiki",
        ),
    )
    api.contribute("recall", "wiki", wiki_recall)
    api.contribute("prompt", "wiki", wiki_prompt)
    api.contribute("dream_step", "lint", DreamStep("lint", lint_step, "skip_lint"))
    api.contribute("dream_step", "reindex", DreamStep("reindex", reindex_step, "skip_reindex"))
    api.contribute(
        "curator_target",
        "wiki",
        CuratorTarget(
            engine="wiki",
            prepare=curator.prepare,
            instructions=curator.instructions,
            persist_tools=("wiki_write_page",),
        ),
    )
    api.contribute("subproject_source", "wiki", PageSource(pages=curator.pages, engine="wiki"))
    api.contribute("self_doc", "wiki", curator.self_doc)
    api.contribute("scaffold", "wiki", curator.scaffold)
    api.contribute(
        "background_op",
        "ingest",
        BackgroundOp(kind="ingest", toolset="ingest", run=run_ingest_job),
    )


# The wiki engine's agent tools — present only when the layout enables the engine.
WIKI_TOOLS: tuple[str, ...] = (
    "wiki_list_pages",
    "wiki_read_page",
    "wiki_search",
    "wiki_write_page",
    "wiki_add_category",
    "wiki_append_log",
    "wiki_ingest",
    "wiki_rename_page",
    "wiki_add",
)


__all__ = ["WIKI_TOOLS", "Wiki", "WikiPageInfo", "ingest_user_message", "register"]
