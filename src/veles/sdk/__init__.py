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
- `veles.sdk.channels` — the platform contract for a channel module.
- `veles.sdk.channel_checks` — checks a channel module's tests run on its spec.
- `veles.sdk.media` — speech-to-text and image description adapters.
- `veles.sdk.providers` — the LLM provider contract and a CLI delegate's base.

`t()` renders a string of the active locale; a module's own strings live in its
`locales/<lang>.toml` and are reached as `t("<module>.<key>")`.
"""

from __future__ import annotations

from veles.core.context import current_origin, current_project
from veles.core.i18n import t
from veles.core.io_utils import load_optional_toml
from veles.core.project import Project, load_project
from veles.core.sanitize import sanitize
from veles.core.slug import normalize_slug, now_timestamp_slug
from veles.core.text import cut_with_note, first_heading, shown, shown_multiline, title_and_summary
from veles.core.timeutil import utc_iso

# `import veles.sdk` makes every part reachable (`veles.sdk.tools.tool`, …).
from veles.sdk import (  # noqa: F401
    channel_checks,
    channels,
    contributions,
    jobs,
    layout,
    media,
    memory,
    providers,
    tools,
)

__all__ = [
    "Project",
    "current_origin",
    "current_project",
    "cut_with_note",
    "first_heading",
    "load_optional_toml",
    "load_project",
    "normalize_slug",
    "now_timestamp_slug",
    "sanitize",
    "shown",
    "shown_multiline",
    "t",
    "title_and_summary",
    "utc_iso",
]
