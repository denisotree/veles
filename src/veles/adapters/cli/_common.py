"""Shared helpers for CLI-delegation adapters."""

from __future__ import annotations

from veles.core.provider import Message


def format_messages_as_prompt(messages: list[Message]) -> str:
    """Render a Veles message list into a markdown-ish flat prompt.

    System/User/Assistant turns each become an H1-headed block. Tool messages
    are skipped — CLI delegates don't carry our tool_call_id chain, and there
    is no canonical place for them in a single-shot prompt.
    """
    parts: list[str] = []
    for m in messages:
        if m.role == "system":
            parts.append(f"# System\n\n{m.content or ''}\n")
        elif m.role == "user":
            parts.append(f"# User\n\n{m.content or ''}\n")
        elif m.role == "assistant":
            parts.append(f"# Assistant\n\n{m.content or ''}\n")
    return "\n".join(parts)
