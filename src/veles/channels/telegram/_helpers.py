"""Constants and misc helpers for the Telegram channel.

Split out from the main gateway file so the class focuses on transport
+ orchestration. Helpers here are pure / stateless."""

from __future__ import annotations

import re as _re
from pathlib import Path

from veles.channels.display import DisplayTier, truncate_for_tier

_TELEGRAM_API = "https://api.telegram.org"
_LONG_POLL_TIMEOUT = 30
# M210: getUpdates retry backoff — 2s doubling to a 60s ceiling. Before this
# the loop retried on a fixed 2s sleep, spamming one WARNING per poll for the
# whole outage (a real offline hour = ~1800 identical lines).
_POLL_RETRY_INITIAL = 2.0
_POLL_RETRY_MAX = 60.0
_PLACEHOLDER_TEXT = "..."
_TELEGRAM_TIER = DisplayTier.HIGH


def _truncate(text: str) -> str:
    return truncate_for_tier(text, _TELEGRAM_TIER)


# Tool-name substring → i18n ack key. The first match wins, so order by
# specificity. Everything unmatched falls back to the generic "working".
_ACK_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("web_search", "web_fetch", "browse", "http"), "telegram.ack_web"),
    (("wiki_add", "ingest", "write_page", "append", "curate"), "telegram.ack_writing_note"),
    (("search", "recall", "query", "grep", "find"), "telegram.ack_searching"),
    (("tool_", "skill_", "author", "install", "delegate", "spawn"), "telegram.ack_building"),
    (("read_file", "read", "open", "cat"), "telegram.ack_reading"),
)


def ack_key_for_tool(tool_name: str) -> str:
    """Map a tool name to the i18n key of the contextual "on it" ack the
    channel shows when the agent's first action is a tool call (rather
    than an immediate text answer)."""
    name = (tool_name or "").lower()
    for needles, key in _ACK_RULES:
        if any(n in name for n in needles):
            return key
    return "telegram.ack_working"


def _build_combined_prompt(
    parts: list[str],
    attachments: list[Path],
    project_root: Path | None,
) -> str:
    """Slice the buffered messages into a single prompt the LLM gets.

    `parts` are the user-visible blocks (comment text, forwarded quote);
    `attachments` are file paths saved under `attachment_dir`. The agent
    learns to call `read_file(rel_path)` from the trailing instruction."""
    if not parts and attachments:
        parts = [
            "I sent you a file. Read it and tell me what you can do with it.",
        ]
    body = "\n\n".join(p.strip() for p in parts if p and p.strip())
    if not attachments:
        return body
    rels: list[str] = []
    for p in attachments:
        try:
            if project_root is not None:
                rels.append(str(p.relative_to(project_root)))
            else:
                rels.append(p.name)
        except ValueError:
            rels.append(p.name)
    listing = ", ".join(f"`{r}`" for r in rels)
    return f"{body}\n\n[Attachments saved: {listing}. Read each via read_file() before answering.]"


def _is_parse_error(exc: BaseException) -> bool:
    """Telegram returns HTTP 400 with `can't parse entities` (or
    `Bad Request: parse entities`) when our HTML is malformed. Detecting
    these lets us drop to plain-text rather than losing the message."""
    msg = str(exc).lower()
    return "parse entit" in msg or "unsupported start tag" in msg


def _html_to_plain(text: str) -> str:
    """Strip HTML tags and decode the three escaped entities so the
    fallback send carries readable plain text instead of `&lt;b&gt;`
    visible to the user."""
    no_tags = _re.sub(r"<[^>]+>", "", text)
    return no_tags.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
