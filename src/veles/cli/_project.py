"""Project lifecycle helpers used by every CLI verb.

These helpers don't depend on the agent loop, so the module is a leaf that is
safe to import from any command body.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from veles.core.modules import (
    ModuleHandle,
    ModuleLoadError,
    ModuleRegistry,
    discover_modules,
    discover_modules_in,
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


def _dedup_by_name(handles: list[ModuleHandle], *, scope: str) -> list[ModuleHandle]:
    """Two module dirs in the same scope sharing a manifest `name`: keep only the
    first (sorted by dir — `discover_modules_in` already sorts) and warn about the rest."""
    seen: dict[str, ModuleHandle] = {}
    out: list[ModuleHandle] = []
    for h in handles:
        if h.name in seen:
            print(
                f"warning: duplicate {scope} module name {h.name!r} at {h.dir} "
                f"(already loading from {seen[h.name].dir}) — ignored",
                file=sys.stderr,
            )
            continue
        seen[h.name] = h
        out.append(h)
    return out


def _admitted(handles: list[ModuleHandle], *, flag: str) -> list[ModuleHandle]:
    """The handles the load gate admits; each refused one is named by its dir."""
    from veles.core.registry.gate import admit_module

    out: list[ModuleHandle] = []
    for handle in handles:
        refusal = admit_module(handle.dir)
        if refusal is None:
            out.append(handle)
            continue
        print(
            f"warning: skipping module {handle.name!r} at {handle.dir}: {refusal} — review "
            f"it, then `veles module approve {flag}{handle.name}`",
            file=sys.stderr,
        )
    return out


def _load_project_modules(project: Project) -> ModuleRegistry:
    """User-level modules (`~/.veles/modules/`) first, then the project's. Every module
    passes the gate first; only then does an approved project module replace a same-named
    user-level one, so an unapproved dir can never disable an approved module."""
    from veles.core.user_paths import user_modules_dir

    project_handles = _dedup_by_name(_admitted(discover_modules(project), flag=""), scope="project")
    overridden = {h.name for h in project_handles}
    user_handles = _dedup_by_name(
        _admitted(discover_modules_in(user_modules_dir()), flag="--user "), scope="user"
    )
    handles: list[ModuleHandle] = []
    for h in user_handles:
        if h.name in overridden:
            print(
                f"warning: module {h.name!r} in the project overrides the user-level one",
                file=sys.stderr,
            )
            continue
        handles.append(h)
    handles.extend(project_handles)
    registry = ModuleRegistry()
    for handle in handles:
        try:
            load_module(handle, registry)
        except ModuleLoadError as exc:
            print(f"warning: skipping module {handle.name!r}: {exc}", file=sys.stderr)
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


def require_project(args: argparse.Namespace) -> Project | None:
    """`_resolve_active_project`, printing the standard error when there is none."""
    project = _resolve_active_project(args)
    if project is None:
        print("error: no Veles project found here. Run `veles init` first.", file=sys.stderr)
    return project


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


# M253: `_warn_if_agents_md_invalid` used to live here and ran on every `run` /
# REPL / ingest / organize. Deleted rather than made opt-out: by
# `agents_md_schema`'s own description the check is "a kindness so the user
# notices when their auto-loaded context is gibberish" — an init/diagnostics
# concern, not a per-turn one. An AGENTS.md can only become non-conforming by
# being hand-edited, which is deliberate, so repeating the complaint every run
# taught nothing and trained the user to ignore stderr. It now lives where
# checks live: `veles schema validate` and `veles doctor`.
