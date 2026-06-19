"""Ingest primitives shared by CLI (`veles add` / `veles ingest`) and TUI
(`/wiki add` from M83). Owns the agent's system prompt and the user
message template so prompt drift can't happen between entry points.

Provider/model/agent construction stays at the call-site — CLI knows
about budget tracking and console output; TUI talks to its widgets via
the Textual event loop. Keeping this module pure ASCII makes it easy to
import from both surfaces without dragging in either runtime.
"""

from __future__ import annotations

INGEST_SYSTEM_PROMPT = (
    "You are the Veles ingest agent. Read the source named by the user and"
    " write a single wiki page summarizing it.\n\n"
    "Workflow:\n"
    "- For URLs (http:// or https://): call fetch_url(url).\n"
    "- For file paths: call read_file(path).\n"
    "- Decide a category. Allowed: 'concepts' (ideas, frameworks),"
    " 'entities' (people, products, organizations), 'sources' (notes about"
    " the raw source itself).\n"
    "- Choose a short kebab-case slug.\n"
    "- Compose a markdown wiki page: H1 title, then a few sections."
    " Keep it focused; cite specific facts.\n"
    "- Call wiki_write_page(category, slug, title, content).\n"
    "- Call wiki_append_log(op='ingest', summary='<one-line description>').\n"
    "- Reply with a one-sentence confirmation that includes the page path."
)


def ingest_user_message(source: str) -> str:
    """The user-side prompt that kicks off an ingest run for `source`."""
    return f"Ingest this source: {source}"


__all__ = ["INGEST_SYSTEM_PROMPT", "ingest_user_message"]
