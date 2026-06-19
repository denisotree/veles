"""TEMPORARY re-export shim — the wiki moved to `veles.modules.wiki` (2026-06-19).

Kept only while import sites are migrated off `veles.core.wiki`; deleted at the
end of the wiki-extraction refactor (see docs/plans/wiki-extraction-to-module.md).
Do not add new imports against this path.
"""

from veles.modules.wiki.wiki import (  # noqa: F401  (re-export shim)
    Wiki,
    WikiPageInfo,
    _fts_escape,
    _normalize_slug,
)
