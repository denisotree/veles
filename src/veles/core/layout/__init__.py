"""Layout-pack architecture (M117, VISION §5.2).

A **layout-pack** declares how a project organises its user-facing
content — directories, writable zones, and the named operations the
agent uses to interact with that content. The default pack ships
inside Veles (`builtin/llm-wiki/`); users can add custom packs to
`<project>/.veles/layouts/<name>/` or `~/.veles/layouts/<name>/`.

VISION §5.2: "core не делает предположений о том, как именно
хранится контент". Project memory (`<cwd>/.veles/`) stays
layout-agnostic; only the user-content side switches.

Public surface:
- `LayoutManifest` — typed manifest model
- `read_manifest(path)` — parse a `layout.toml` into `LayoutManifest`
- `discover_layouts(project)` — returns the list of available packs
  in priority order (project → user → builtin)
- `find_layout(project, name)` — pick a specific pack by name
- `LAYOUT_DEFAULT` — `"llm-wiki"`, the dropdown default in `veles init`
- `apply_scaffold(pack, root, name)` — pack-driven init skeleton (M162)
- `wiki_enabled(project)` / `engine_enabled(project, name)` — content
  engine activation checks (M162)
"""

from veles.core.layout.discovery import (
    LAYOUT_DEFAULT,
    LayoutDirectory,
    discover_layouts,
    find_layout,
)
from veles.core.layout.engines import (
    clear_engine_cache,
    engine_enabled,
    wiki_enabled,
)
from veles.core.layout.manifest import (
    LayoutManifest,
    LayoutManifestError,
    LayoutOperation,
    LayoutWritableZone,
    read_manifest,
)
from veles.core.layout.scaffold import apply_scaffold
from veles.core.layout.writable import is_writable, writable_zones

__all__ = [
    "LAYOUT_DEFAULT",
    "LayoutDirectory",
    "LayoutManifest",
    "LayoutManifestError",
    "LayoutOperation",
    "LayoutWritableZone",
    "apply_scaffold",
    "clear_engine_cache",
    "discover_layouts",
    "engine_enabled",
    "find_layout",
    "is_writable",
    "read_manifest",
    "wiki_enabled",
    "writable_zones",
]
