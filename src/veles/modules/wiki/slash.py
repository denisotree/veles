"""The wiki engine's `/wiki` REPL command (moved from the REPL's builtins, M83).

`/wiki add <path|url>` — the agent ingests a source into the wiki.
`/wiki query <question>` — the agent answers from the wiki with
wiki_search/wiki_read_page. Both hand a prompt to the live agent turn, so the
REPL doesn't fork a second runtime."""

from __future__ import annotations

from veles.sdk import Project
from veles.sdk.contributions import SlashReply

from .ingest import ingest_user_message


def wiki_command(project: Project, line: str) -> SlashReply:
    del project
    if not line:
        return SlashReply("/wiki: expected add <path|url> | query <question>", error=True)
    parts = line.split(maxsplit=1)
    sub = parts[0]
    arg = parts[1].strip() if len(parts) > 1 else ""
    if sub == "add":
        if not arg:
            return SlashReply("/wiki add needs a path or URL", error=True)
        return SlashReply(f"ingesting {arg} into the wiki…", submit_prompt=ingest_user_message(arg))
    if sub == "query":
        if not arg:
            return SlashReply("/wiki query needs a question string", error=True)
        prompt = (
            f"Search the project wiki to answer: {arg}\n\n"
            "Use wiki_search and wiki_read_page tools to find relevant pages, "
            "then summarize what we already know. Cite page paths in your reply."
        )
        return SlashReply(f"querying wiki for: {arg}", submit_prompt=prompt)
    return SlashReply(f"/wiki: unknown subcommand {sub!r}; try add/query", error=True)
