"""Prompt-injection scrubber for any text that ends up in the system prompt.

Veles loads `AGENTS.md`, the wiki `INDEX.md`, and individual wiki pages into
the LLM context. If those files contain hostile content (intentional or not),
the model can be steered into following instructions hidden inside the data.
This module provides a baseline scrubber that:

1. Strips invisible/zero-width unicode characters (they cannot legitimately
   belong to readable markdown).
2. Replaces well-known injection phrases with `<scrubbed:…>` markers — the
   model still sees that something was filtered, but cannot follow the
   instruction.
3. Logs each finding to stderr with a `source_label` so the user knows where
   the injection came from.

This is a baseline, not a complete jailbreak gauntlet. It catches the lazy
attacks. Future milestones can add allow-lists or more detectors.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass

_INVISIBLE_CHARS = re.compile(
    r"[​‌‍⁠﻿᠎­]"  # ZWSP, ZWNJ, ZWJ, WJ, BOM, MV, soft hyphen
    r"|[\U000E0000-\U000E007F]"  # Unicode tag characters
)

_PHRASE_DETECTORS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "ignore-instructions",
        re.compile(
            r"ignore\s+(?:the\s+|all\s+|any\s+)?(?:previous|above|prior)\s+"
            r"(?:instructions|prompt|rules|directives)",
            re.IGNORECASE,
        ),
        "<scrubbed:ignore-instructions>",
    ),
    (
        "disregard-rules",
        re.compile(
            r"disregard\s+(?:the\s+|all\s+|any\s+)?(?:previous|above|original|system)\s+"
            r"(?:instructions|prompt|rules|directives)",
            re.IGNORECASE,
        ),
        "<scrubbed:disregard-rules>",
    ),
    (
        "system-prompt-impersonation",
        re.compile(
            r"<\s*/?\s*(?:system|im_start|im_end)\s*\|?>",
            re.IGNORECASE,
        ),
        "<scrubbed:system-tag>",
    ),
    (
        "you-are-now",
        re.compile(
            r"you\s+are\s+now\s+(?:a|an|the)?\s*\w+",
            re.IGNORECASE,
        ),
        "<scrubbed:you-are-now>",
    ),
    (
        "pretend-to-be",
        re.compile(
            r"pretend\s+(?:to\s+be|you\s+are|that\s+you\s+are)",
            re.IGNORECASE,
        ),
        "<scrubbed:pretend>",
    ),
]


@dataclass(slots=True, frozen=True)
class InjectionFinding:
    pattern: str
    snippet: str  # capped to 60 chars


def scan_for_injection(
    text: str, *, source_label: str = "<unknown>"
) -> tuple[str, list[InjectionFinding]]:
    """Return (cleaned_text, findings) and log each finding to stderr."""
    cleaned = text
    findings: list[InjectionFinding] = []

    invisible_count = 0

    def _record_invisible(_match: re.Match[str]) -> str:
        nonlocal invisible_count
        invisible_count += 1
        return ""

    cleaned = _INVISIBLE_CHARS.sub(_record_invisible, cleaned)
    if invisible_count > 0:
        findings.append(
            InjectionFinding(pattern="invisible-chars", snippet=f"{invisible_count} char(s)")
        )

    for name, pat, repl in _PHRASE_DETECTORS:
        for match in pat.finditer(cleaned):
            findings.append(InjectionFinding(pattern=name, snippet=match.group(0)[:60]))
        cleaned = pat.sub(repl, cleaned)

    if findings:
        for f in findings:
            print(
                f"warning: prompt-injection pattern {f.pattern!r} in {source_label}: {f.snippet!r}",
                file=sys.stderr,
            )
    return cleaned, findings
