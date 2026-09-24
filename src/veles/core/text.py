"""Small text shaping shared by recall, tools and prompts."""

from __future__ import annotations

import re

_SUMMARY_CHAR_CAP = 200
_OPENING_FENCE = re.compile(r"^```[\w-]*[ \t]*\n?")


def ellipsize(text: str, cap: int) -> str:
    """`text` on one line, cut to `cap` characters with a trailing `…` when longer."""
    line = text.strip().replace("\n", " ")
    return line if len(line) <= cap else line[: cap - 1].rstrip() + "…"


def cut_with_note(text: str, cap: int, note: str) -> str:
    """`text` unchanged when it fits in `cap`, else cut so that it plus `note` does."""
    return text if len(text) <= cap else text[: cap - len(note)] + note


def strip_code_fence(text: str) -> str:
    """An LLM reply without a wrapping ```lang … ``` fence, if it has one."""
    text = text.strip()
    if not text.startswith("```"):
        return text
    text = _OPENING_FENCE.sub("", text, count=1)
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def first_heading(text: str) -> str:
    """The first markdown heading, else the first non-empty line cut to 80 chars."""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            return stripped.lstrip("# ").strip()
        return stripped[:80]
    return ""


def title_and_summary(content: str, fallback: str) -> tuple[str, str]:
    """A markdown page's H1 (or `fallback`) and its first paragraph, capped."""
    title = fallback
    summary_lines: list[str] = []
    seen_h1 = False
    for line in content.splitlines():
        stripped = line.strip()
        if not seen_h1 and stripped.startswith("# "):
            title = stripped[2:].strip() or fallback
            seen_h1 = True
            continue
        if seen_h1 and stripped:
            if stripped.startswith("#"):
                if summary_lines:
                    break
                continue
            summary_lines.append(stripped)
            if sum(len(s) for s in summary_lines) >= _SUMMARY_CHAR_CAP:
                break
    return title, ellipsize(" ".join(summary_lines), _SUMMARY_CHAR_CAP)


__all__ = ["cut_with_note", "ellipsize", "first_heading", "strip_code_fence", "title_and_summary"]
