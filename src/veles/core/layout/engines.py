"""Layout-engine resolution — the single chokepoint for "is the wiki
content engine active in this project?" (M162).

Core ships optional *content engines* (today: `wiki` — the Karpathy
LLM-Wiki machinery in `modules/wiki/` and its `wiki_*` tools). A layout
pack activates an engine by declaring it in its manifest:

    [layout.engines]
    wiki = true

Every call site that touches wiki machinery conditionally goes through
`wiki_enabled(project)` rather than re-implementing manifest lookups.
The result is cached per (project root, layout name, manifest mtime) —
recall and agent-build are hot paths, manifest edits are rare.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from veles.core.project import Project

_ENGINE_WIKI = "wiki"

# (resolved project root, layout name) -> (manifest mtime, enabled engines)
_cache: dict[tuple[str, str], tuple[float, tuple[str, ...]]] = {}


def engine_enabled(project: Project | None, engine: str) -> bool:
    """True when the project's active layout pack declares `engine`.

    No project, or a layout name that resolves to no pack → no engines
    (a project that opted out of any content layout gets no content
    machinery)."""
    if project is None:
        return False
    return engine in _enabled_engines(project)


def wiki_enabled(project: Project | None) -> bool:
    return engine_enabled(project, _ENGINE_WIKI)


def clear_engine_cache() -> None:
    """Test hook — drop all memoised manifest lookups."""
    _cache.clear()


def _enabled_engines(project: Project) -> tuple[str, ...]:
    from veles.core.layout.discovery import find_layout

    key = (str(project.root.resolve()), project.layout_name)
    pack = find_layout(project.layout_name, project)
    if pack is None:
        _cache.pop(key, None)
        return ()
    mtime = _manifest_mtime(pack.manifest.source)
    cached = _cache.get(key)
    if cached is not None and cached[0] == mtime:
        return cached[1]
    engines = pack.manifest.engines
    _cache[key] = (mtime, engines)
    return engines


def _manifest_mtime(source: Path | None) -> float:
    if source is None:
        return 0.0
    try:
        return source.stat().st_mtime
    except OSError:
        return 0.0


__all__ = ["clear_engine_cache", "engine_enabled", "wiki_enabled"]
