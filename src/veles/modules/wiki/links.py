"""Deterministic `[[wiki-link]]` resolution (M249).

Nothing in Veles checked whether the links a page writes actually point at
existing pages. `find_orphans` looks the other way (inbound references) and
matches on `rel_path` substrings, so it never parses `[[...]]` at all.

That gap made a confident false claim indistinguishable from a real audit.
Observed 2026-09-02: an agent wrote 15 pages into a live vault, then logged
"Cross-link audit passed … all resolve their [[wiki-link]] targets (15 unique
targets, NONE unresolved)", and the CHECK advisor accepted the goal on that
basis. Measured afterwards: **102 of 159 links did not resolve** — the pages
were named `nabokov-aesthetic-principles.md` but linked as
`[[Nabokov's aesthetic principles]]`. The model had itself identified
`[[slug|Display]]` as the vault's idiom while planning, then failed to apply it
while writing, and nothing contradicted it.

So the check is a fact computed from the filesystem and handed back in the tool
result, where the model cannot narrate over it.

Matching follows Obsidian's forgiving behaviour rather than exact equality:
case-insensitive, and punctuation/whitespace folded to single hyphens, so
`[[Speak, Memory]]` resolves to `speak-memory.md`. That is deliberately looser
than the filesystem — a link that Obsidian would open must not be reported
broken.
"""

from __future__ import annotations

import re

# `[[target]]`, `[[target|Display]]`, `[[target#Heading]]`, `[[target^block]]`.
_LINK_RE = re.compile(r"\[\[([^\]\n]+)\]\]")
_NON_SLUG = re.compile(r"[^a-z0-9]+")


def normalize_link(target: str) -> str:
    """Fold a link target (or a page stem) to its comparison key."""
    head = target.split("|", 1)[0]
    head = head.split("#", 1)[0].split("^", 1)[0]
    return _NON_SLUG.sub("-", head.strip().lower()).strip("-")


def parse_links(text: str) -> list[str]:
    """Every `[[...]]` target in `text`, in order, duplicates included."""
    return [m.group(1) for m in _LINK_RE.finditer(text or "")]


def unresolved_links(text: str, known: set[str]) -> list[str]:
    """Link targets in `text` that match no page in `known`.

    `known` is a set of page stems (file names without `.md`); it is normalised
    here so callers can pass raw stems. Returns each distinct unresolved target
    once, preserving first-seen order so the message is stable.
    """
    keys = {normalize_link(k) for k in known}
    seen: set[str] = set()
    out: list[str] = []
    for raw in parse_links(text):
        key = normalize_link(raw)
        if not key or key in keys or key in seen:
            continue
        seen.add(key)
        out.append(raw)
    return out


def render_link_warning(unresolved: list[str], *, total: int, limit: int = 8) -> str:
    """One-line report for a tool result. Empty string when everything resolves.

    Deliberately a warning and not an error: pages are usually written in a
    batch, so a link to a page that does not exist *yet* is normal mid-run. The
    point is that the model is told, every time, instead of being free to assume.
    """
    if not unresolved:
        return ""
    shown = ", ".join(repr(t) for t in unresolved[:limit])
    more = f" (+{len(unresolved) - limit} more)" if len(unresolved) > limit else ""
    return (
        f" — WARNING: {len(unresolved)} of {total} [[links]] do not resolve to an "
        f"existing page: {shown}{more}. Use [[slug|Display]] with the target's "
        f"actual file slug, or create the missing pages."
    )


__all__ = [
    "normalize_link",
    "parse_links",
    "render_link_warning",
    "unresolved_links",
]
