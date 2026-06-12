"""Attachment validation helpers for the Telegram channel.

Veles only accepts textual attachments (≤ 5 MB) — anything else is
politely refused so the agent doesn't waste a turn on a binary it can't
read. The validation is split into pure helpers here; the actual
download/persist lives on the gateway."""

from __future__ import annotations

import re
from pathlib import Path

from veles.channels.telegram_format import escape_html

_MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024
_TEXTUAL_MIME_PREFIXES = ("text/",)
_TEXTUAL_MIME_LITERALS = frozenset(
    {
        "application/json",
        "application/xml",
        "application/yaml",
        "application/x-yaml",
        "application/toml",
        "application/x-toml",
    }
)
_TEXTUAL_EXTENSIONS = frozenset(
    {
        ".md",
        ".txt",
        ".rst",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".csv",
        ".tsv",
        ".py",
        ".js",
        ".ts",
        ".go",
        ".rs",
        ".java",
        ".c",
        ".cpp",
        ".h",
        ".sh",
        ".sql",
        ".html",
        ".css",
        ".xml",
        ".ini",
        ".env",
        ".log",
        ".diff",
        ".patch",
    }
)
_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _is_textual(name: str, mime: str) -> bool:
    mime_l = (mime or "").lower()
    if any(mime_l.startswith(p) for p in _TEXTUAL_MIME_PREFIXES):
        return True
    if mime_l in _TEXTUAL_MIME_LITERALS:
        return True
    ext = Path(name or "").suffix.lower()
    return ext in _TEXTUAL_EXTENSIONS


def _reject_reason(name: str, mime: str, size: int) -> str | None:
    if size > _MAX_ATTACHMENT_BYTES:
        kb = size // 1024
        return f"📎 File larger than 5 MB ({kb} KB) — refused."
    if not _is_textual(name, mime):
        safe = escape_html(name or "file")
        mime_disp = escape_html(mime) if mime else "unknown"
        return (
            f"📎 I only handle text files. "
            f"<code>{safe}</code> ({mime_disp}) doesn't look like text."
        )
    return None


def _safe_filename(name: str) -> str:
    """Drop directory parts, collapse anything non-`[A-Za-z0-9._-]` to
    `_`, trim leading/trailing punctuation, cap at 80 chars. The UUID
    prefix added by the caller guarantees uniqueness regardless."""
    base = Path(name or "file").name or "file"
    cleaned = _SAFE_FILENAME_RE.sub("_", base).strip("._") or "file"
    return cleaned[:80]
