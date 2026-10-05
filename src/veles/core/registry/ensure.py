"""One place for "the project needs an extension that isn't installed".

The needs: the project's layout pack is missing (`LayoutNeed`), its pack asks
for a content engine no loaded module contributes (`EngineNeed`), a declared
channel's platform (`PlatformNeed`) or a named LLM provider (`ProviderNeed`) is
not installed — the last two install without asking (the config decided). With a
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
_OFFICIAL_PROVIDERS = frozenset({"antigravity-cli"})


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


@dataclass(frozen=True, slots=True)
class ProviderNeed:
    """An LLM provider named by config, a flag or a route that no catalogue entry provides."""

    name: str


Need = LayoutNeed | EngineNeed | PlatformNeed | ProviderNeed

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
    if isinstance(need, ProviderNeed) and need.name in _OFFICIAL_PROVIDERS:
        return f"public:official/{need.name}"
    return None


def ensure_extension(
    need: Need,
    project: Project | None,
    *,
    interactive: bool,
    auto: bool = False,
    reason: str | None = None,
) -> bool:
    """True when `need` is met by installing it now; False (after one warning per
    need per process) otherwise. Never raises.

    `auto`: the user already decided (a channel declared in their config) — the
    install runs without a terminal and without asking, and says what it installs
    and why (`reason`, e.g. "declared in [channels.telegram]"). Only from the
    user's connected registries and only an unambiguous ref (`_spec`); anything
    else is a warning and nothing is installed."""
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
                + f" ({reason or 'declared in your config'})",
                file=sys.stderr,
            )
        else:
            print(f"{_label(need)} is not installed; it is in the registry as {found.ref}.")
        # An engine, a channel platform or a provider serves every project that asks for it.
        _install(
            found,
            project=project,
            user_scope=isinstance(need, (EngineNeed, PlatformNeed, ProviderNeed)),
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
    prefix = f"daemon.{session}.channels" if session else "channels"
    for need in channel_needs(project, session):
        why = f"declared in [{prefix}.{need.name}]"
        installed = (
            ensure_extension(need, None, interactive=False, auto=True, reason=why) or installed
        )
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

    # Into the live registry, not a scoped one: the pick then needs them loaded
    # (`ensure_platform_interactive`), and an entrypoint runs once per process.
    _load_user_modules_into_live()
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
    from veles.core.platforms import list_platforms

    _load_user_modules_into_live()
    if name in list_platforms():
        return True
    if not ensure_extension(PlatformNeed(name), None, interactive=True):
        return False
    _load_user_modules_into_live()
    return name in list_platforms()


def ensure_provider(name: str, *, reason: str) -> bool:
    """`name` is in the provider catalogue — already, or installed now from the
    user's connected registries: naming a provider is the decision, as declaring a
    channel is (release C §7). False for a retired or unknown name."""
    from veles.core.providers import RETIRED, find_provider

    if find_provider(name) is not None:
        return True
    _load_user_modules_into_live()
    if find_provider(name) is not None or name in RETIRED:
        return find_provider(name) is not None
    if not _offered(name):
        return False  # a typo nobody offers: the caller says "unknown provider"
    if ensure_extension(ProviderNeed(name), None, interactive=False, auto=True, reason=reason):
        _load_user_modules_into_live()
    return find_provider(name) is not None


def _offered(name: str) -> bool:
    """A registry offers provider `name` — the official ref, or a cached-registry
    extension whose `provides` lists it (no network)."""
    from veles.core.registry import catalog

    return bool(ref_for(ProviderNeed(name)) or catalog.providers_of(f"provider:{name}"))


_ROUTE_SOURCES = {
    "project-provider": "named in [engine] provider",
    "user-provider": "named as your default provider",
}


def routed_provider_needs(project: Project) -> list[tuple[str, str]]:
    """`(provider, why)` for each provider a routed task names that the catalogue
    lacks but a registry offers. A name nobody offers (a typo) is doctor's to report."""
    from veles.core.providers import find_provider
    from veles.core.routing.ensemble import KNOWN_TASKS, effective_route

    out: dict[str, str] = {}
    for task in sorted(KNOWN_TASKS):
        try:
            provider, _model, source = effective_route(task, project)
        except Exception:  # an unconfigured task routes nowhere — nothing to install
            continue
        if provider in out or find_provider(provider) is not None:
            continue
        if _offered(provider):
            out[provider] = _ROUTE_SOURCES.get(source, f"named in [routing.tasks].{task}")
    return list(out.items())


def ensure_routed_providers(project: Project) -> bool:
    """`ensure_provider` for every provider `routed_provider_needs` finds."""
    installed = False
    for provider, why in routed_provider_needs(project):
        installed = ensure_provider(provider, reason=why) or installed
    return installed


def _load_user_modules_into_live() -> None:
    """User-level modules (where a platform installs) into the live registry —
    a process that loaded no modules (the daemon picker, `veles init`) gets one;
    a module already loaded is not loaded twice."""
    from veles.core.module_loading import load_user_modules
    from veles.core.modules import current_module_registry, set_module_registry

    live = current_module_registry()
    registry = load_user_modules(into=live)
    if live is None:
        set_module_registry(registry)


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

    # With the official registry connected, the official ref is the only
    # candidate (a stale cache is refreshed by `_resolve`); another provider
    # counts only when that registry is not connected.
    if ref is not None and _connected(ref.partition(":")[0]):
        return ref
    points: dict[type, str] = {PlatformNeed: "platform", ProviderNeed: "provider"}
    point = points.get(type(need), "engine")
    refs = catalog.providers_of(f"{point}:{need.name}")
    if len(refs) == 1:
        return refs[0]
    if refs:
        _warn(need, " or ".join(refs), reason="several extensions provide it — pick one")
    else:
        _warn(need, need.name, reason="no registry extension provides it")
    return None


def _connected(registry: str) -> bool:
    from veles.core.registry.config import RegistryConfigError, get_source

    try:
        get_source(registry)
    except RegistryConfigError:
        return False
    return True


def _resolve(spec: str) -> Any:
    """`resolve`, and once more after refreshing the named registry: its cache
    may predate the package (an upgrade that moved a feature into the registry)."""
    from veles.core.registry import catalog, repo
    from veles.core.registry.config import get_source

    try:
        return catalog.resolve(spec)
    except catalog.ResolveError:
        registry = spec.rpartition(":")[0]
        if not registry or not _connected(registry):
            raise
    repo.update(get_source(registry))
    return catalog.resolve(spec)


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
    if isinstance(need, ProviderNeed):
        return f"LLM provider {need.name!r}"
    return f"content engine {need.name!r}"


def _warn(need: Need, ref: str, *, reason: str = "") -> None:
    if need in _warned:
        return
    _warned.add(need)
    why = f" ({reason})" if reason else ""
    # A missing layout or engine degrades the run; a missing platform or provider
    # is the caller's to report (no channel to start, no model to run on).
    degrades = "" if isinstance(need, (PlatformNeed, ProviderNeed)) else " — working without it"
    print(
        f"warning: {_label(need)} is not installed{why}{degrades}. "
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
