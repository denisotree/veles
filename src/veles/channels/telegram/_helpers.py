"""Constants and misc helpers for the Telegram channel.

Split out from the main gateway file so the class focuses on transport
+ orchestration. Helpers here are pure / stateless."""

from __future__ import annotations

import re as _re
from pathlib import Path

from veles.channels.display import DisplayTier, truncate_for_tier

_TELEGRAM_API = "https://api.telegram.org"
_LONG_POLL_TIMEOUT = 30
_PLACEHOLDER_TEXT = "..."
_TELEGRAM_TIER = DisplayTier.HIGH


def _truncate(text: str) -> str:
    return truncate_for_tier(text, _TELEGRAM_TIER)


def _build_combined_prompt(
    parts: list[str], attachments: list[Path], project_root: Path | None,
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
    return (
        f"{body}\n\n"
        f"[Attachments saved: {listing}. "
        f"Read each via read_file() before answering.]"
    )


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
    return (
        no_tags.replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
    )
