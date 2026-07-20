"""Markdown → Telegram-HTML conversion.

Telegram's bot API has no Markdown renderer worth shipping LLM output
into: MarkdownV2 requires escaping 18 special characters and reliably
breaks on the kind of slightly-off Markdown LLMs produce. HTML is the
strict subset Telegram does parse predictably — only `<`, `>`, `&` need
escaping, and a fixed whitelist of tags is allowed.

This module converts CommonMark (via `markdown-it-py`) into the
Telegram-allowed subset:

    <b> <strong>   <i> <em>   <u>  <s> <strike> <del>
    <code>  <pre>  <a href="…">  <blockquote>  <tg-spoiler>

Anything Telegram doesn't render is collapsed to a sensible visual
substitute (headings → bold, lists → bullets, tables → `<pre>` aligned).

Three public functions:
- `escape_html(text)` — entity-encode the three special chars.
- `markdown_to_telegram_html(md)` — full pipeline.
- `html_safe_truncate(html, limit)` — chop without orphaning open tags.
"""

from __future__ import annotations

from typing import Any

from markdown_it import MarkdownIt
from markdown_it.token import Token

_TELEGRAM_LIMIT = 4000  # Telegram's hard cap is 4096; leave headroom.

_md = MarkdownIt("commonmark", {"breaks": True, "linkify": True}).enable("table")


def escape_html(text: str) -> str:
    """Replace the three characters Telegram's HTML parser reads as
    markup. Order matters: `&` first so we don't double-escape entities
    we emit ourselves."""
    if not text:
        return text
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _escape_href(url: str) -> str:
    """URL goes inside `href="…"`. Telegram tolerates raw `&` here but
    we entity-encode it for safety. We strip control chars and refuse
    schemes other than http/https/tg/mailto."""
    if not url:
        return ""
    cleaned = "".join(c for c in url if c >= " ")
    lowered = cleaned.lower().strip()
    safe_schemes = ("http://", "https://", "tg://", "mailto:", "/")
    if not any(lowered.startswith(s) for s in safe_schemes):
        return ""
    return cleaned.replace("&", "&amp;").replace('"', "%22")


def markdown_to_telegram_html(md: str) -> str:
    """Convert a Markdown string into Telegram-allowed HTML.

    Robust to LLM-produced quirks (unclosed bold, headings beyond h6,
    nested lists, language tags on code fences). Never raises — a
    parser issue falls back to escaped plain text."""
    if not md:
        return ""
    try:
        tokens = _md.parse(md)
    except Exception:
        return escape_html(md)
    renderer = _TelegramRenderer()
    return renderer.render(tokens).strip()


def html_safe_truncate(html: str, limit: int = _TELEGRAM_LIMIT) -> str:
    """Cut `html` to at most `limit` characters without leaving open
    tags or half-formed entities. Open tags found in the kept prefix
    are closed in reverse order; a trailing partial entity (`&am`) is
    dropped before truncation."""
    if len(html) <= limit:
        return html
    kept = html[:limit]
    # Drop a trailing partial entity so the truncated text doesn't end
    # mid-`&amp;`. Entities are `&...;`, at most ~6 chars.
    amp = kept.rfind("&")
    if amp >= 0 and ";" not in kept[amp:]:
        kept = kept[:amp]
    # Track open tags. We assume tags well-formed because we generated
    # them — `<tag>` opens, `</tag>` closes, `<tag/>` self-closes.
    open_stack: list[str] = []
    i = 0
    while i < len(kept):
        if kept[i] != "<":
            i += 1
            continue
        end = kept.find(">", i)
        if end < 0:
            # An open `<` at the cut boundary — drop it.
            kept = kept[:i]
            break
        tag_body = kept[i + 1 : end]
        if tag_body.endswith("/"):
            pass  # self-closing
        elif tag_body.startswith("/"):
            name = tag_body[1:].split()[0]
            if open_stack and open_stack[-1] == name:
                open_stack.pop()
        else:
            name = tag_body.split()[0]
            open_stack.append(name)
        i = end + 1
    closers = "".join(f"</{tag}>" for tag in reversed(open_stack))
    suffix = "…" + closers
    # If adding the suffix overflows the limit, trim the kept prefix
    # further. Bounded by `limit` so loop is finite.
    while len(kept) + len(suffix) > limit and kept:
        kept = kept[:-1]
    return kept + suffix


def _atomize(html: str) -> list[tuple[str, str]]:
    """Break `html` into atomic units the splitter must not cut through.

    Yields `(kind, text)` where kind ∈ {"tag", "entity", "text"}. Tags
    (`<...>`) and entities (`&...;`) are indivisible; text runs carry no
    `<`/`&` and may be split anywhere."""
    units: list[tuple[str, str]] = []
    i, n = 0, len(html)
    while i < n:
        c = html[i]
        if c == "<":
            end = html.find(">", i)
            if end < 0:
                units.append(("text", html[i:]))
                break
            units.append(("tag", html[i : end + 1]))
            i = end + 1
        elif c == "&":
            end = html.find(";", i, i + 12)
            if end >= 0:
                units.append(("entity", html[i : end + 1]))
                i = end + 1
            else:
                units.append(("text", "&"))
                i += 1
        else:
            j = i
            while j < n and html[j] not in "<&":
                j += 1
            units.append(("text", html[i:j]))
            i = j
    return units


def _tag_effect(tag: str) -> tuple[str, str | None]:
    """Classify a `<...>` unit. Returns `(kind, name)` where kind ∈
    {"open","close","self"}; name is the tag name (None for self-close)."""
    body = tag[1:-1].strip()
    if body.startswith("/"):
        return "close", body[1:].split()[0] if body[1:].split() else ""
    if body.endswith("/"):
        return "self", None
    return "open", (body.split()[0] if body.split() else "")


def split_telegram_html(html: str, limit: int = _TELEGRAM_LIMIT) -> list[str]:
    """Split rendered Telegram-HTML into chunks each ≤ `limit` chars,
    every chunk independently valid. Tags open at a chunk boundary are
    closed at its end and reopened at the start of the next chunk, so
    formatting (bold, nested styles) continues across messages. Entities
    are never cut; long text runs split at whitespace when possible."""
    if len(html) <= limit:
        return [html]

    chunks: list[str] = []
    openers: list[str] = []  # full opener strings, e.g. '<a href="x">'
    names: list[str] = []  # parallel tag names, for closing
    cur: list[str] = []
    cur_len = 0
    prefix_len = 0  # length of the reopener prefix at this chunk's start

    def closers_str() -> str:
        return "".join(f"</{name}>" for name in reversed(names))

    def start_chunk() -> None:
        nonlocal cur, cur_len, prefix_len
        pre = "".join(openers)
        cur = [pre] if pre else []
        cur_len = len(pre)
        prefix_len = len(pre)

    def flush() -> None:
        # Only emit if there's real content beyond the reopener prefix.
        if cur_len <= prefix_len:
            return
        chunks.append("".join(cur) + closers_str())
        start_chunk()

    for kind, text in _atomize(html):
        if kind == "text":
            remaining = text
            while remaining:
                room = limit - cur_len - len(closers_str())
                if room <= 0:
                    flush()
                    room = limit - cur_len - len(closers_str())
                if len(remaining) <= room:
                    cur.append(remaining)
                    cur_len += len(remaining)
                    remaining = ""
                else:
                    cut = remaining.rfind(" ", prefix_len if not cur else 1, room)
                    if cut <= 0:
                        cut = remaining.rfind("\n", 0, room)
                    if cut <= 0:
                        cut = room
                    cur.append(remaining[:cut])
                    cur_len += cut
                    remaining = remaining[cut:]
                    flush()
            continue

        # tag / entity — atomic. Reserve room to also close open tags.
        effect, name = ("self", None) if kind == "entity" else _tag_effect(text)
        extra = len(f"</{name}>") if effect == "open" else 0
        if cur_len + len(text) + len(closers_str()) + extra > limit:
            flush()
        cur.append(text)
        cur_len += len(text)
        if effect == "open" and name:
            openers.append(text)
            names.append(name)
        elif effect == "close" and names and names[-1] == name:
            openers.pop()
            names.pop()

    if cur_len > prefix_len:
        chunks.append("".join(cur) + closers_str())
    return chunks


# ---- renderer ----


class _TelegramRenderer:
    """Walks markdown-it tokens, emits Telegram-allowed HTML."""

    __slots__ = ("_list_stack", "_out")

    def __init__(self) -> None:
        self._out: list[str] = []
        # Stack of (kind, counter) for nested lists; kind ∈ {"ul","ol"}.
        self._list_stack: list[tuple[str, int]] = []

    def render(self, tokens: list[Token]) -> str:
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            handler = _BLOCK_HANDLERS.get(tok.type)
            if handler is not None:
                handler(self, tok)
            elif tok.type == "inline":
                self._render_inline(tok.children or [])
            i += 1
        return "".join(self._out)

    # ---- block-level handlers ----

    def open_heading(self, tok: Token) -> None:
        self._out.append("<b>")

    def close_heading(self, tok: Token) -> None:
        self._out.append("</b>\n\n")

    def open_paragraph(self, tok: Token) -> None:
        # Inside a list item we don't want extra blank lines.
        if not self._inside_list_item():
            pass
        # Open paragraph emits nothing; close emits the break.

    def close_paragraph(self, tok: Token) -> None:
        self._out.append("\n\n" if not self._inside_list_item() else "\n")

    def open_blockquote(self, tok: Token) -> None:
        self._out.append("<blockquote>")

    def close_blockquote(self, tok: Token) -> None:
        self._out.append("</blockquote>\n")

    def fence(self, tok: Token) -> None:
        info = (tok.info or "").strip().split(None, 1)
        lang = info[0] if info else ""
        content = escape_html(tok.content.rstrip("\n"))
        if lang:
            self._out.append(
                f'<pre><code class="language-{escape_html(lang)}">{content}</code></pre>\n'
            )
        else:
            self._out.append(f"<pre>{content}</pre>\n")

    def code_block(self, tok: Token) -> None:
        self._out.append(f"<pre>{escape_html(tok.content.rstrip())}</pre>\n")

    def hr(self, tok: Token) -> None:
        self._out.append("\n──────────\n")

    def open_bullet_list(self, tok: Token) -> None:
        self._list_stack.append(("ul", 0))

    def close_bullet_list(self, tok: Token) -> None:
        if self._list_stack:
            self._list_stack.pop()
        if not self._list_stack:
            self._out.append("\n")

    def open_ordered_list(self, tok: Token) -> None:
        start = int(tok.attrGet("start") or 1)
        self._list_stack.append(("ol", start - 1))

    def close_ordered_list(self, tok: Token) -> None:
        if self._list_stack:
            self._list_stack.pop()
        if not self._list_stack:
            self._out.append("\n")

    def open_list_item(self, tok: Token) -> None:
        if not self._list_stack:
            return
        kind, counter = self._list_stack[-1]
        # Indent for nested levels by two spaces per outer list.
        indent = "  " * (len(self._list_stack) - 1)
        if kind == "ul":
            self._out.append(f"{indent}• ")
        else:
            counter += 1
            self._list_stack[-1] = (kind, counter)
            self._out.append(f"{indent}{counter}. ")

    def close_list_item(self, tok: Token) -> None:
        # Trim trailing extra newline produced by paragraph_close.
        if self._out and self._out[-1].endswith("\n\n"):
            self._out[-1] = self._out[-1][:-1]

    # ---- tables — flatten into a monospaced <pre> grid ----

    def table(self, tokens: list[Token], idx: int) -> int:
        """Handled out-of-band — see `_render_table`. Returns new index."""
        return idx

    def _inside_list_item(self) -> bool:
        return bool(self._list_stack)

    # ---- inline ----

    def _render_inline(self, children: list[Token]) -> None:
        for child in children:
            handler = _INLINE_HANDLERS.get(child.type)
            if handler is not None:
                handler(self, child)
            elif child.type == "text":
                self._out.append(escape_html(child.content))


def _open(tag: str):
    def _fn(self: _TelegramRenderer, tok: Token) -> None:
        self._out.append(f"<{tag}>")

    return _fn


def _close(tag: str):
    def _fn(self: _TelegramRenderer, tok: Token) -> None:
        self._out.append(f"</{tag}>")

    return _fn


def _link_open(self: _TelegramRenderer, tok: Token) -> None:
    href = _escape_href(tok.attrGet("href") or "")
    if href:
        self._out.append(f'<a href="{href}">')
    # If href unsafe, just skip the tag — text content still flows.


def _link_close(self: _TelegramRenderer, tok: Token) -> None:
    # If we didn't emit an opener (unsafe href), don't emit closer either.
    last_a = "".join(self._out).rfind("<a ")
    last_close = "".join(self._out).rfind("</a>")
    if last_a > last_close:
        self._out.append("</a>")


def _code_inline(self: _TelegramRenderer, tok: Token) -> None:
    self._out.append(f"<code>{escape_html(tok.content)}</code>")


def _softbreak(self: _TelegramRenderer, tok: Token) -> None:
    self._out.append("\n")


def _hardbreak(self: _TelegramRenderer, tok: Token) -> None:
    self._out.append("\n")


def _html_inline(self: _TelegramRenderer, tok: Token) -> None:
    # LLMs sometimes paste raw HTML (`<br>`, `<div>`) — Telegram would
    # reject most of it. Escape the lot so it shows as literal text.
    self._out.append(escape_html(tok.content))


_BLOCK_HANDLERS: dict[str, Any] = {
    "heading_open": _TelegramRenderer.open_heading,
    "heading_close": _TelegramRenderer.close_heading,
    "paragraph_open": _TelegramRenderer.open_paragraph,
    "paragraph_close": _TelegramRenderer.close_paragraph,
    "blockquote_open": _TelegramRenderer.open_blockquote,
    "blockquote_close": _TelegramRenderer.close_blockquote,
    "fence": _TelegramRenderer.fence,
    "code_block": _TelegramRenderer.code_block,
    "hr": _TelegramRenderer.hr,
    "bullet_list_open": _TelegramRenderer.open_bullet_list,
    "bullet_list_close": _TelegramRenderer.close_bullet_list,
    "ordered_list_open": _TelegramRenderer.open_ordered_list,
    "ordered_list_close": _TelegramRenderer.close_ordered_list,
    "list_item_open": _TelegramRenderer.open_list_item,
    "list_item_close": _TelegramRenderer.close_list_item,
    # Tables collapse to a paragraph with a pre-block computed inline.
    "table_open": lambda self, tok: self._out.append("<pre>"),
    "table_close": lambda self, tok: self._out.append("</pre>\n"),
    "thead_open": lambda self, tok: None,
    "thead_close": lambda self, tok: self._out.append("─" * 4 + "\n"),
    "tbody_open": lambda self, tok: None,
    "tbody_close": lambda self, tok: None,
    "tr_open": lambda self, tok: None,
    "tr_close": lambda self, tok: self._out.append("\n"),
    "th_open": lambda self, tok: self._out.append(""),
    "th_close": lambda self, tok: self._out.append("\t"),
    "td_open": lambda self, tok: self._out.append(""),
    "td_close": lambda self, tok: self._out.append("\t"),
}

_INLINE_HANDLERS: dict[str, Any] = {
    "strong_open": _open("b"),
    "strong_close": _close("b"),
    "em_open": _open("i"),
    "em_close": _close("i"),
    "s_open": _open("s"),
    "s_close": _close("s"),
    "code_inline": _code_inline,
    "link_open": _link_open,
    "link_close": _link_close,
    "softbreak": _softbreak,
    "hardbreak": _hardbreak,
    "html_inline": _html_inline,
}


__all__ = [
    "escape_html",
    "html_safe_truncate",
    "markdown_to_telegram_html",
    "split_telegram_html",
]
