"""Project lifecycle helpers used by every CLI verb.

Extracted from `cli/__init__.py` in M46 final. These helpers don't
depend on the agent loop and have no internal cross-references, so the
module is a pure leaf that's safe to import from any command body.

`cli/__init__.py` re-exports each `_<name>` for backward compatibility
with `from veles.cli import _foo` and `monkeypatch.setattr("veles.cli._foo", ...)`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from veles.core.agents_md_schema import (
    RECOMMENDED_SECTIONS as _AGENTS_RECOMMENDED_SECTIONS,
)
from veles.core.agents_md_schema import (
    validate as _validate_agents_md,
)
from veles.core.modules import (
    ModuleLoadError,
    ModuleRegistry,
    discover_modules,
    load_module,
)
from veles.core.project import (
    Project,
    ProjectNotFound,
    find_project_root,
    load_project,
)
from veles.core.project_registry import Registry as ProjectRegistry
from veles.core.slug import normalize_slug as _normalize_slug


def _load_project_modules(project: Project) -> ModuleRegistry:
    registry = ModuleRegistry()
    for handle in discover_modules(project):
        try:
            load_module(handle, registry)
        except ModuleLoadError as exc:
            print(
                f"warning: skipping module {handle.name!r}: {exc}",
                file=sys.stderr,
            )
    return registry


def _resolve_active_project(args: argparse.Namespace) -> Project | None:
    explicit = getattr(args, "project_root", None)
    if explicit:
        root = Path(explicit).resolve()
        try:
            return load_project(root)
        except ProjectNotFound:
            return None
    found = find_project_root()
    if found is None:
        return None
    return load_project(found)


def _register_project(project: Project, *, slug: str | None = None) -> None:
    """Add `project` to the multi-project registry (best-effort)."""
    try:
        reg = ProjectRegistry.load()
        reg.add(project, slug=slug)
        reg.save()
    except OSError as exc:
        print(f"warning: could not update project registry: {exc}", file=sys.stderr)


def _touch_active_project(project: Project) -> None:
    """Bump `last_active_at` for `project` if it's already in the registry.

    Called on every `veles run`; silently no-op for unregistered projects
    (init didn't run, e.g. the project was created before M33).
    """
    try:
        reg = ProjectRegistry.load()
        slug_candidates = (
            _normalize_slug(project.name) or project.root.name,
            project.root.name,
        )
        for slug in slug_candidates:
            if reg.touch(slug) is not None:
                reg.save()
                return
        # Unknown project — register it lazily so future runs find it.
        reg.add(project)
        reg.save()
    except OSError:
        pass


def _warn_if_agents_md_invalid(project: Project) -> None:
    """Best-effort warn when the auto-loaded AGENTS.md lacks recommended
    sections. Never blocks; never raises. Called at the start of run /
    ingest / query / lint so the user notices once per command and can
    fix it via `veles schema edit`."""
    p = project.agents_md_path
    if not p.is_file():
        return
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    result = _validate_agents_md(text)
    if result.ok:
        return
    missing = ", ".join(result.missing)
    expected = ", ".join(_AGENTS_RECOMMENDED_SECTIONS)
    print(
        f"warning: AGENTS.md is missing recommended sections: {missing} "
        f"(expected: {expected}). Run `veles schema edit` to fix.",
        file=sys.stderr,
    )
