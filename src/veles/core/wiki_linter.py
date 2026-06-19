"""TEMPORARY re-export shim — moved to `veles.modules.wiki.linter` (2026-06-19).
Deleted at the end of the wiki-extraction refactor. Do not import against this path.
"""

from veles.modules.wiki.linter import (  # noqa: F401  (re-export shim)
    LintFinding,
    LintReport,
    _find_oldest_date,
    _title_tokens,
    find_duplicates,
    find_orphans,
    find_stale,
    render_report,
    run_lint,
)
