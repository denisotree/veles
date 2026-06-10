"""Vertical subprojects (M41) — child projects rooted at subdirectories.

VISION §5.2: a Veles project can have child projects rooted at any
subdirectory (`<root>/<sub>/.veles/project.toml`). Each subproject is a
full project (own AGENTS.md, wiki, sources, sessions) — vertical
decomposition of a single codebase, useful when one repo owns multiple
domains (`myorg/frontend`, `myorg/backend`) and you want each to keep
its own knowledge base while still being part of one workspace.

State of truth lives at `<parent>/.veles/subprojects.json`:

    {
        "subprojects": [
            {"slug": "frontend", "path": "./frontend", "description": "React UI"},
            {"slug": "backend",  "path": "./backend",  "description": "FastAPI"}
        ]
    }

Resolution rules:
- `find_project_root(cwd)` returns the *nearest* enclosing project, so
  cd-ing into `myorg/frontend/src` makes `frontend` the active project
  even though `myorg` is also one.
- `find_parent_project(p)` walks up from `p.root.parent` to find the
  enclosing project, if any. Returns `None` for top-level projects.
- `load_subprojects(p)` reads the registry only — the file-system is NOT
  scanned for unregistered `.veles/` directories. A child initialised
  outside `init_subproject` stays invisible until explicit register.

For M41, `MemoryRouter.recall` composes *downward*: the active project's
wiki search is augmented with each registered child's wiki search, with
a smaller per-child cap. Upward (child → parent) and sibling traversal
are M41b.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from veles.core.project import (
    Project,
    ProjectAlreadyExists,
    find_project_root,
    init_project,
    load_project,
)

_SUBPROJECTS_FILENAME = "subprojects.json"


@dataclass(frozen=True, slots=True)
class Subproject:
    slug: str
    path: str
    description: str = ""


def subprojects_path(project: Project) -> Path:
    return project.state_dir / _SUBPROJECTS_FILENAME


def load_subprojects(project: Project) -> list[Subproject]:
    """Return registered subprojects, or [] if file missing / corrupt / malformed."""
    path = subprojects_path(project)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, dict):
        return []
    raw = data.get("subprojects")
    if not isinstance(raw, list):
        return []
    out: list[Subproject] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        slug = entry.get("slug")
        path_val = entry.get("path")
        if not isinstance(slug, str) or not slug:
            continue
        if not isinstance(path_val, str) or not path_val:
            continue
        description_raw = entry.get("description")
        description = description_raw if isinstance(description_raw, str) else ""
        out.append(Subproject(slug=slug, path=path_val, description=description))
    return out


def register_subproject(project: Project, sub: Subproject) -> None:
    """Insert / overwrite a subproject (keyed on slug) in the parent's registry."""
    kept = [s for s in load_subprojects(project) if s.slug != sub.slug]
    kept.append(sub)
    kept.sort(key=lambda s: s.slug)
    _atomic_write(project, kept)


def unregister_subproject(project: Project, slug: str) -> bool:
    """Remove a subproject by slug. Returns True iff it existed."""
    current = load_subprojects(project)
    filtered = [s for s in current if s.slug != slug]
    if len(filtered) == len(current):
        return False
    _atomic_write(project, filtered)
    return True


def resolve_subproject_path(project: Project, sub: Subproject) -> Path:
    """Resolve a subproject's `path` field against the parent root."""
    return (project.root / sub.path).resolve()


def find_parent_project(project: Project) -> Project | None:
    """Walk up from `project.root.parent` looking for an enclosing project.

    Returns the closest ancestor project, or `None` for top-level projects
    (no enclosing `.veles/project.toml` above this root).
    """
    parent_dir = project.root.parent
    if parent_dir == project.root:
        return None
    parent_root = find_project_root(parent_dir)
    if parent_root is None:
        return None
    return load_project(parent_root)


def init_subproject(
    parent: Project,
    subdir: str,
    *,
    name: str | None = None,
    description: str = "",
) -> Project:
    """Initialise a Veles project at `<parent.root>/<subdir>` and register it.

    `subdir` is interpreted relative to `parent.root`. Refuses if the
    resolved path is outside the parent (no `..` escape, no absolute
    path), equals the parent root, or already hosts an initialised
    project. Slug for the registry is the subproject's normalised name
    (from `init_project`).
    """
    rel_str = subdir.strip()
    if not rel_str:
        raise ValueError("subdir must not be empty")
    if rel_str.startswith("/") or ".." in Path(rel_str).parts:
        raise ValueError(f"invalid subdir {subdir!r}: must be a relative path inside parent root")
    parent_resolved = parent.root.resolve()
    subroot = (parent_resolved / rel_str).resolve()
    if subroot == parent_resolved:
        raise ValueError("subdir cannot equal the parent root")
    try:
        rel = subroot.relative_to(parent_resolved)
    except ValueError as exc:
        raise ValueError(f"subdir {subroot} resolves outside parent {parent_resolved}") from exc
    if (subroot / ".veles" / "project.toml").is_file():
        raise ProjectAlreadyExists(f"project already initialised at {subroot}")
    subproject = init_project(subroot, name=name)
    rel_path = "./" + rel.as_posix()
    register_subproject(
        parent,
        Subproject(slug=subproject.name, path=rel_path, description=description),
    )
    return subproject


def _atomic_write(project: Project, subs: list[Subproject]) -> None:
    project.state_dir.mkdir(parents=True, exist_ok=True)
    target = subprojects_path(project)
    body = {"subprojects": [asdict(s) for s in subs]}
    text = json.dumps(body, indent=2, ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp_name, target)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise
