"""TEMPORARY re-export shim — moved to `veles.modules.wiki.tools` (2026-06-19).

Importing this re-runs the `@tool` decorators in `veles.modules.wiki.tools`,
so wiki tools still register while `core/tools/builtin/__init__.py` imports
this path. Deleted at the end of the wiki-extraction refactor.
"""

from veles.modules.wiki.tools import (  # noqa: F401  (re-export shim)
    _infer_title_from_text,
    _kebab,
    wiki_append_log,
    wiki_ingest,
    wiki_list_pages,
    wiki_read_page,
    wiki_search,
    wiki_write_page,
)
