"""The public surface for Veles modules.

A module (built in or from a registry) imports Veles only through `veles.sdk`
and its submodules; core internals can then move without breaking modules.
Everything here is a re-export — the very objects core uses. The name lists are
pinned by `tests/test_sdk_surface.py`; changing one goes into the CHANGELOG.

- `veles.sdk` — projects, the active-run context, small text/slug/time helpers.
- `veles.sdk.contributions` — contribution types (`Engine`, `ToolSet`, …).
- `veles.sdk.tools` — the `@tool` decorator, risk classes, path and write guards.
- `veles.sdk.memory` — recall hits, memory providers, memory artefacts.
- `veles.sdk.layout` — layout packs, context files, subprojects.
- `veles.sdk.jobs` — background jobs, worker agents, delegation depth.
"""

from __future__ import annotations

from veles.core.context import current_origin, current_project
from veles.core.io_utils import load_optional_toml
from veles.core.project import Project, load_project
from veles.core.slug import normalize_slug, now_timestamp_slug
from veles.core.text import first_heading, shown, title_and_summary
from veles.core.timeutil import utc_iso

# `import veles.sdk` makes every part reachable (`veles.sdk.tools.tool`, …).
from veles.sdk import contributions, jobs, layout, memory, tools  # noqa: F401

__all__ = [
    "Project",
    "current_origin",
    "current_project",
    "first_heading",
    "load_optional_toml",
    "load_project",
    "normalize_slug",
    "now_timestamp_slug",
    "shown",
    "title_and_summary",
    "utc_iso",
]
