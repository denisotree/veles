"""One place for "the project needs an extension that isn't installed".

Two kinds of need: the project's layout pack is missing (`LayoutNeed`), or its
pack asks for a content engine no loaded module contributes (`EngineNeed`). With a
terminal the user is offered the install (the normal confirmation, dependencies
included); without one — or when the registry is unreachable, the user declines,
or nothing provides it — Veles warns once per need per process with the command
to run, and carries on without it. Nothing here ever raises, and nothing touches
the project's data.

Layouts that used to ship with Veles (`MIGRATED_LAYOUTS`) and the wiki engine
always come from `public:official/<name>`.
"""

from __future__ import annotations

import contextlib
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from veles.core.project import Project

MIGRATED_LAYOUTS = frozenset({"llm-wiki", "notes"})
_OFFICIAL_ENGINES = frozenset({"wiki"})


@dataclass(frozen=True, slots=True)
class LayoutNeed:
    name: str


@dataclass(frozen=True, slots=True)
class EngineNeed:
    name: str


Need = LayoutNeed | EngineNeed

_warned: set[Need] = set()


def needs_for(project: Project) -> list[Need]:
    """What the project asks for that isn't here. Engines are checked against the
    loaded contributions (`engine:<name>`), not module directory names."""
    from veles.core.contributions import contributions
    from veles.core.layout.discovery import find_layout

    pack = find_layout(project.layout_name, project)
    if pack is None:
        return [LayoutNeed(project.layout_name)]
    present = {c.name for c in contributions("engine")}
    return [EngineNeed(e) for e in pack.manifest.engines if e not in present]


def ref_for(need: Need) -> str | None:
    """The registry ref to install for `need`, when it can be named without a
    catalog lookup."""
    if isinstance(need, LayoutNeed) and need.name in MIGRATED_LAYOUTS:
        return f"public:official/{need.name}"
    if isinstance(need, EngineNeed) and need.name in _OFFICIAL_ENGINES:
        return f"public:official/{need.name}"
    return None


def ensure_extension(need: Need, project: Project | None, *, interactive: bool) -> bool:
    """True when `need` is met by installing it now; False (after one warning per
    need per process) otherwise. Never raises."""
    try:
        if not interactive:
            _warn(need, ref_for(need) or need.name)
            return False
        spec = _spec(need)
        if spec is None:
            return False
        found = _resolve(spec)
        print(f"{_label(need)} is not installed; it is in the registry as {found.ref}.")
        # An engine module serves every project whose pack asks for it.
        _install(found, project=project, user_scope=isinstance(need, EngineNeed))
        return True
    except Exception as exc:  # registry down, declined, bad manifest, anything at all
        _warn(need, ref_for(need) or need.name, reason=str(exc))
        return False


def ensure_project_extensions(project: Project, *, interactive: bool) -> bool:
    """`ensure_extension` for every need of `project`; True when anything got
    installed (the caller reloads modules then)."""
    installed = False
    try:
        needs = needs_for(project)
    except Exception:
        return False
    for need in needs:
        installed = ensure_extension(need, project, interactive=interactive) or installed
    return installed


def install_hint(project: Project) -> str | None:
    """`veles registry install …` for the project's missing layout or engines, or
    None when nothing is missing. For error messages."""
    try:
        needs = needs_for(project)
    except Exception:
        return None
    if not needs:
        return None
    refs = " ".join(ref_for(n) or n.name for n in needs)
    return f"veles registry update && veles registry install {refs}"


def available_layouts() -> list[str]:
    """Layout names to offer in `veles init` / the wizard: installed packs (the
    default first), then layouts in the cached registries (no network) — picking
    one of those installs it."""
    from veles.core.layout.discovery import discover_layouts
    from veles.core.project import LAYOUT_DEFAULT
    from veles.core.registry.catalog import search

    names = [p.manifest.name for p in discover_layouts(None)]
    with contextlib.suppress(Exception):  # no readable registry → installed packs only
        found, _ = search(kind="layout", sync_missing=False)
        names += [f.ext.name for f in found]
    ordered = [LAYOUT_DEFAULT, *names]
    return list(dict.fromkeys(ordered))


def reset_warnings() -> None:
    """Test hook."""
    _warned.clear()


def _spec(need: Need) -> str | None:
    ref = ref_for(need)
    if ref is not None:
        return ref
    if isinstance(need, LayoutNeed):
        return need.name  # `resolve` reports a missing or ambiguous name
    from veles.core.registry import catalog

    refs = catalog.providers_of(f"engine:{need.name}")
    if len(refs) == 1:
        return refs[0]
    if refs:
        _warn(need, " or ".join(refs), reason="several extensions provide it — pick one")
    else:
        _warn(need, need.name, reason="no registry extension provides it")
    return None


def _resolve(spec: str) -> Any:
    from veles.core.registry.catalog import resolve

    return resolve(spec)


def _install(found: Any, *, project: Project | None, user_scope: bool) -> None:
    from veles.core.registry.install import install

    install(found, project=project, user_scope=user_scope)


def _label(need: Need) -> str:
    if isinstance(need, LayoutNeed):
        return f"layout {need.name!r}"
    return f"content engine {need.name!r}"


def _warn(need: Need, ref: str, *, reason: str = "") -> None:
    if need in _warned:
        return
    _warned.add(need)
    why = f" ({reason})" if reason else ""
    print(
        f"warning: {_label(need)} is not installed{why} — working without it. "
        f"Install: `veles registry update && veles registry install {ref}`",
        file=sys.stderr,
    )


__all__ = [
    "MIGRATED_LAYOUTS",
    "EngineNeed",
    "LayoutNeed",
    "available_layouts",
    "ensure_extension",
    "ensure_project_extensions",
    "install_hint",
    "needs_for",
    "ref_for",
]
