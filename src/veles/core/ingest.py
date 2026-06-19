"""TEMPORARY re-export shim — moved to `veles.modules.wiki.ingest` (2026-06-19).
Deleted at the end of the wiki-extraction refactor. Do not import against this path.
"""

from veles.modules.wiki.ingest import (  # noqa: F401  (re-export shim)
    INGEST_SYSTEM_PROMPT,
    ingest_user_message,
)
