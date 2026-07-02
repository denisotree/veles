"""`veles layout sync` — re-apply the active layout pack's scaffold to an
existing project.

`apply_scaffold` runs only at `veles init`; when a pack later gains new
categories/dirs (e.g. the wiki pack adding diary/tasks/projects), existing
projects never materialise them until the next write. `sync` re-runs the
idempotent scaffold + `Wiki.ensure_layout()` so the new structure exists on
disk — which also makes it visible in the injected workspace map, so the agent
can see the target structure to migrate into.
"""

from __future__ import annotations

import argparse

from veles.core.project import Project


def cmd_layout(args: argparse.Namespace, project: Project) -> int:
    if getattr(args, "layout_command", None) != "sync":
        print("usage: veles layout sync")
        return 2
    return _sync(project)


def _sync(project: Project) -> int:
    from veles.core.layout.discovery import find_layout
    from veles.core.layout.engines import wiki_enabled
    from veles.core.layout.scaffold import apply_scaffold

    before = _dir_set(project)
    pack = find_layout(project.layout_name, project)
    # `name` is the AGENTS.md {name}/title substitution — the PROJECT name, not
    # the layout name (passing the layout name re-titles a default AGENTS.md).
    apply_scaffold(pack, project.root, project.name)
    if wiki_enabled(project):
        from veles.modules.wiki.wiki import Wiki

        Wiki(project.wiki_root).ensure_layout()
    after = _dir_set(project)

    created = sorted(after - before)
    if created:
        print(f"synced layout {project.layout_name!r}; created:")
        for rel in created:
            print(f"  {rel}/")
    else:
        print(f"layout {project.layout_name!r} already in sync; nothing to create")
    return 0


def _dir_set(project: Project) -> set[str]:
    """Relative dirs under the project root (excluding .veles), for a
    before/after diff of what `sync` created."""
    root = project.root
    out: set[str] = set()
    for p in root.rglob("*"):
        if p.is_dir() and ".veles" not in p.relative_to(root).parts:
            out.add(p.relative_to(root).as_posix())
    return out
