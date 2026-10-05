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
_OFFICIAL_PLATFORMS = frozenset({"telegram"})


@dataclass(frozen=True, slots=True)
class LayoutNeed:
    name: str


@dataclass(frozen=True, slots=True)
class EngineNeed:
    name: str


@dataclass(frozen=True, slots=True)
class PlatformNeed:
    """A channel declared in config whose platform no loaded module provides."""

    name: str


Need = LayoutNeed | EngineNeed | PlatformNeed

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
    if isinstance(need, PlatformNeed) and need.name in _OFFICIAL_PLATFORMS:
        return f"public:official/{need.name}"
    return None


def ensure_extension(
    need: Need, project: Project | None, *, interactive: bool, auto: bool = False
) -> bool:
    """True when `need` is met by installing it now; False (after one warning per
    need per process) otherwise. Never raises.

    `auto`: the user already decided (a channel declared in their config) — the
    install runs without a terminal and without asking, and says what it installs
    and why. Only from the user's connected registries and only an unambiguous
    ref (`_spec`); anything else is a warning and nothing is installed."""
    try:
        if not interactive and not auto:
            _warn(need, ref_for(need) or need.name)
            return False
        spec = _spec(need)
        if spec is None:
            return False
        found = _resolve(spec)
        if auto:
            print(
                f"installing {found.ref} {getattr(found.ext, 'version', '')}".rstrip()
                + f" (declared in [channels.{need.name}])",
                file=sys.stderr,
            )
        else:
            print(f"{_label(need)} is not installed; it is in the registry as {found.ref}.")
        # An engine or a channel platform serves every project that asks for it.
        _install(
            found,
            project=project,
            user_scope=isinstance(need, (EngineNeed, PlatformNeed)),
            preapproved=auto,
        )
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


def ensure_layout(name: str, *, interactive: bool) -> bool:
    """True when layout `name` is installed, or got installed now (offered at a
    terminal, with its dependencies)."""
    from veles.core.layout.discovery import find_layout

    if find_layout(name, None) is not None:
        return True
    return ensure_extension(LayoutNeed(name), None, interactive=interactive)


def layout_or_default(name: str, *, interactive: bool) -> str:
    """The layout a new project gets when the user picked `name` in a wizard:
    `name` when it is here or got installed now, else the default (said aloud —
    `ensure_extension` has already printed why and how to install it)."""
    from veles.core.project import LAYOUT_DEFAULT

    if name == LAYOUT_DEFAULT or ensure_layout(name, interactive=interactive):
        return name
    print(f"Creating a {LAYOUT_DEFAULT!r} project instead of {name!r}.", file=sys.stderr)
    return LAYOUT_DEFAULT


def channel_needs(project: Project, session: str | None = None) -> list[PlatformNeed]:
    """Enabled channels declared for the daemon (`[channels.*]`, or a named
    session's `[daemon.<s>.channels.*]`) whose platform no loaded module provides.
    Kept apart from `needs_for`: that one runs at every REPL start, a channel
    module is the daemon's business (and `veles channel`'s, and doctor's)."""
    from veles.core.platforms import list_platforms
    from veles.core.project_config import list_channel_configs, load_project_config

    have = set(list_platforms())
    declared = list_channel_configs(load_project_config(project), daemon_session=session)
    return [PlatformNeed(name) for name, _ in declared if name not in have]


def ensure_channel_platforms(project: Project, session: str | None = None) -> list[str]:
    """Install (automatically — the config is the user's decision) the platform
    module of every declared channel that lacks one, load what got installed into
    the live module registry, and return the platforms still missing."""
    from veles.core.module_loading import load_project_modules
    from veles.core.modules import current_module_registry, set_module_registry

    installed = False
    for need in channel_needs(project, session):
        installed = ensure_extension(need, None, interactive=False, auto=True) or installed
    if installed:
        live = current_module_registry()
        registry = load_project_modules(project, into=live)
        if live is None:
            set_module_registry(registry)
    return [n.name for n in channel_needs(project, session)]


def available_platforms() -> list[str]:
    """Channel platforms to offer in a wizard: the installed ones (contributed by
    a loaded module) first, then the `platform:<name>` providers in the cached
    registries (no network) — picking one of those installs it."""
    from veles.core.platforms import list_platforms
    from veles.core.registry.catalog import search

    names = list_platforms()
    with contextlib.suppress(Exception):  # no readable registry → installed platforms only
        found, _ = search(kind="module", sync_missing=False)
        names += [
            p.split(":", 1)[1] for f in found for p in f.ext.provides if p.startswith("platform:")
        ]
    return list(dict.fromkeys(names))


def ensure_platform_interactive(name: str) -> bool:
    """`name` is installed, or got installed now with the normal confirmation (a
    wizard pick) and its module loaded into the live registry."""
    from veles.core.module_loading import load_user_modules
    from veles.core.modules import current_module_registry, set_module_registry
    from veles.core.platforms import list_platforms

    if name in list_platforms():
        return True
    if not ensure_extension(PlatformNeed(name), None, interactive=True):
        return False
    live = current_module_registry()
    registry = load_user_modules(into=live)
    if live is None:
        set_module_registry(registry)
    return name in list_platforms()


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
    if isinstance(need, LayoutNeed):
        return ref or need.name  # `resolve` reports a missing or ambiguous name
    from veles.core.registry import catalog

    point = "platform" if isinstance(need, PlatformNeed) else "engine"
    refs = catalog.providers_of(f"{point}:{need.name}")
    # The official ref wins when it is there — or when nothing is cached yet
    # (`resolve` syncs it); a single other provider is unambiguous too.
    if ref is not None and (ref in refs or not refs):
        return ref
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


def _install(
    found: Any, *, project: Project | None, user_scope: bool, preapproved: bool = False
) -> None:
    from veles.core.registry.install import install

    install(found, project=project, user_scope=user_scope, preapproved=preapproved)


def _label(need: Need) -> str:
    if isinstance(need, LayoutNeed):
        return f"layout {need.name!r}"
    if isinstance(need, PlatformNeed):
        return f"channel platform {need.name!r}"
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
    "PlatformNeed",
    "available_layouts",
    "available_platforms",
    "channel_needs",
    "ensure_channel_platforms",
    "ensure_extension",
    "ensure_layout",
    "ensure_platform_interactive",
    "ensure_project_extensions",
    "install_hint",
    "layout_or_default",
    "needs_for",
    "ref_for",
]
