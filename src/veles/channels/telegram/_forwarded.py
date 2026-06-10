"""Forwarded-message detection and rendering for the Telegram channel.

Telegram sends a `forward_*` collection on messages that were forwarded
from elsewhere. The agent should see the forwarded body as a quote,
not mix it up with the user's own comment — that's what
`_render_forwarded` enforces."""

from __future__ import annotations

from typing import Any

_FORWARD_KEYS = (
    "forward_origin",
    "forward_from",
    "forward_from_chat",
    "forward_sender_name",
)


def _has_forward(message: dict[str, Any]) -> bool:
    return any(message.get(k) for k in _FORWARD_KEYS)


def _forward_source(message: dict[str, Any]) -> str:
    origin = message.get("forward_origin")
    if isinstance(origin, dict):
        chat = origin.get("chat")
        if isinstance(chat, dict) and chat.get("title"):
            return str(chat["title"])
        sender = origin.get("sender_user")
        if isinstance(sender, dict):
            for key in ("username", "first_name"):
                if sender.get(key):
                    return str(sender[key])
        if origin.get("sender_user_name"):
            return str(origin["sender_user_name"])
    chat = message.get("forward_from_chat")
    if isinstance(chat, dict):
        return str(chat.get("title") or chat.get("username") or "channel")
    user = message.get("forward_from")
    if isinstance(user, dict):
        return str(user.get("username") or user.get("first_name") or "user")
    name = message.get("forward_sender_name")
    if name:
        return str(name)
    return ""


def _render_forwarded(message: dict[str, Any]) -> str:
    """Turn a forwarded message into a quote block prefixed with `↪️
    Forwarded from <src>:`. The body is indented with `> ` so the
    agent can't mistake the quote for the user's own request."""
    src = _forward_source(message)
    body = (message.get("text") or message.get("caption") or "").strip() or "(empty)"
    head = f"↪️ Forwarded from {src}:" if src else "↪️ Forwarded message:"
    quoted = "\n".join(f"> {line}" for line in body.splitlines())
    return f"{head}\n{quoted}"
