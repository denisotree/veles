"""Slug normalisation — shared by wiki pages, memory artefacts, skills,
modules, and project names.

Extracted from the wiki code (M160): slugging is core text
infrastructure, not a wiki concern — five non-wiki modules need it.
"""

from __future__ import annotations

import datetime as _dt
import re
import unicodedata

_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_slug(raw: str) -> str:
    """Return a kebab-case ASCII slug. Empty inputs yield 'untitled'."""
    nfkd = unicodedata.normalize("NFKD", raw)
    ascii_only = nfkd.encode("ascii", "ignore").decode("ascii").lower()
    cleaned = _SLUG_NON_ALNUM.sub("-", ascii_only).strip("-")
    return cleaned or "untitled"


def now_timestamp_slug() -> str:
    """Return a compact UTC timestamp (`YYYYMMDDTHHMMSSZ`) for filenames.

    Shared by the context compressor and the dream loop to name session /
    insight artefacts under `.veles/memory/`."""
    return _dt.datetime.now(tz=_dt.UTC).strftime("%Y%m%dT%H%M%SZ")
