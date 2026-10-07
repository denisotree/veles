"""Plugin/module discovery, loading, and hook dispatch.

Modules live in `<project>/.veles/modules/<name>/` with a `module.toml`
manifest pointing to a Python entrypoint. At command start, `cli.main`
walks `discover_modules`, calls `load_module` for each (which executes
`register(api)`), and stashes the populated `ModuleRegistry` in a
ContextVar so `fire_hook` can dispatch from `agent.run` and `_dispatch`
without threading the registry through Agent's constructor.

M24 wired four observability-only hooks (`pre_turn`/`post_turn`/
`pre_tool_call`/`post_tool_call`); M26 adds session-lifecycle hooks
(`on_session_start`/`on_session_end`) and gives `pre_tool_call` veto
authority via `VetoResult`. A callback returning a `VetoResult` cancels
the tool call without invoking its handler; subsequent observers still
see the dispatch via `post_tool_call` with `error="vetoed by ..."`.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import sys
from collections.abc import Callable, Iterator
from contextvars import ContextVar, Token
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from veles.core.contributions import (
    CONTRIBUTION_POINTS,
    Contribution,
    check,
    refuse_builtin_collisions,
)
from veles.core.module_manifest import (
    ManifestError,
    ModuleManifest,
    entrypoint_file,
    parse_manifest,
)
from veles.core.project import Project
from veles.core.text import shown

HOOK_NAMES: tuple[str, ...] = (
    "pre_turn",
    "post_turn",
    "pre_tool_call",
    "post_tool_call",
    "on_session_start",
    "on_session_end",
)
_MANIFEST_FILENAME = "module.toml"


class ModuleLoadError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ModuleHandle:
    name: str
    manifest: ModuleManifest
    dir: Path


@dataclass(frozen=True, slots=True)
class VetoResult:
    """A `pre_tool_call` callback returns this to cancel the dispatch.

    `module_name` is filled in by `fire_hook` from the registered hook
    owner; callbacks may leave it empty. Future M37 trust-level can
    extend with severity / policy fields without breaking this contract.
    """

    reason: str
    module_name: str = ""


HookFn = Callable[[dict[str, Any]], VetoResult | None]
ProviderFactory = Callable[[dict[str, Any]], object | None]


class ModuleRegistry:
    def __init__(self) -> None:
        self._hooks: dict[str, list[tuple[str, HookFn]]] = {n: [] for n in HOOK_NAMES}
        self._contributions: dict[str, list[Contribution]] = {}
        self.modules: list[str] = []
        # Module name → its directory, for modules loaded from one (their `skills/`).
        self.module_dirs: dict[str, Path] = {}
        # Module name → why it didn't load into this registry (`module_loading`).
        self.load_errors: dict[str, str] = {}

    def add_contribution(self, point: str, name: str, module_name: str, obj: object) -> None:
        """`ValueError` for an unknown point, an object the point doesn't take, or a
        name already contributed to a keyed point."""
        check(point, name, obj)
        self._refuse_taken(point, name)
        self._contributions.setdefault(point, []).append(
            Contribution(point, name, obj, module_name)
        )

    def contributions(self, point: str) -> list[Contribution]:
        return list(self._contributions.get(point, ()))

    def _refuse_taken(self, point: str, name: str) -> None:
        """`ValueError` when a keyed point already has a contribution named `name`."""
        if not CONTRIBUTION_POINTS[point].keyed:
            return
        for c in self._contributions.get(point, ()):
            if c.name == name:
                raise ValueError(f"{point} {name!r} is already registered by {c.module!r}")

    def add_hook(self, hook_name: str, module_name: str, fn: HookFn) -> None:
        if hook_name not in HOOK_NAMES:
            raise ValueError(f"unknown hook {hook_name!r}; expected one of {HOOK_NAMES}")
        self._hooks[hook_name].append((module_name, fn))

    def iter_hooks(self, hook_name: str) -> Iterator[tuple[str, HookFn]]:
        return iter(self._hooks.get(hook_name, []))

    def add_memory_provider(self, name: str, module_name: str, factory: ProviderFactory) -> None:
        from veles.core.registry.model import is_slug

        if not is_slug(name):
            raise ValueError(f"memory provider name {name!r} must match [a-z0-9][a-z0-9-]*")
        self.add_contribution("memory", name, module_name, factory)

    def iter_memory_providers(self) -> Iterator[tuple[str, str, ProviderFactory]]:
        for c in self.contributions("memory"):
            yield c.name, c.module, c.obj  # type: ignore[misc]

    def merge_from(self, other: ModuleRegistry, module_name: str) -> None:
        """Fold `other` (a scratch registry a single module's `register()` populated)
        into self, then record `module_name` as loaded.

        Called only once `register()` has returned without raising, so this is the one
        moment a module's registrations become visible outside its own load attempt —
        `load_module` builds each module a fresh scratch `ModuleRegistry`, and only a
        clean `register()` return reaches this call, making registration atomic: a
        module that raises never leaves hooks or providers behind (`api.add_hook` /
        `api.add_memory_provider` only ever mutate the scratch copy).

        A contribution name that collides with one already in self (for a keyed point)
        is treated as a load failure too: raises `ValueError` (the caller turns it into
        a `ModuleLoadError`) before anything is merged, so a colliding module leaves
        nothing behind either — checked first so the merge itself is all-or-nothing.
        """
        for point, entries in other._contributions.items():
            for c in entries:
                self._refuse_taken(point, c.name)
        for hook_name, hooks in other._hooks.items():
            self._hooks[hook_name].extend(hooks)
        for point, entries in other._contributions.items():
            self._contributions.setdefault(point, []).extend(entries)
        self.modules.append(module_name)


class ModuleAPI:
    """Thin facade passed to a module's `register(api)` function."""

    def __init__(self, registry: ModuleRegistry, module_name: str) -> None:
        self._registry = registry
        self._module_name = module_name

    def add_hook(self, hook_name: str, fn: HookFn) -> None:
        self._registry.add_hook(hook_name, self._module_name, fn)

    def add_memory_provider(self, name: str, factory: ProviderFactory) -> None:
        self._registry.add_memory_provider(name, self._module_name, factory)

    def contribute(self, point: str, name: str, obj: object) -> None:
        """Add `obj` to contribution `point` (see `veles.core.contributions`)."""
        self._registry.add_contribution(point, name, self._module_name, obj)


# ---- ContextVar for the active registry ----


_module_registry: ContextVar[ModuleRegistry | None] = ContextVar(
    "veles_module_registry", default=None
)


def current_module_registry() -> ModuleRegistry | None:
    return _module_registry.get()


def set_module_registry(reg: ModuleRegistry | None) -> Token:
    return _module_registry.set(reg)


def reset_module_registry(token: Token) -> None:
    _module_registry.reset(token)


# ---- Discovery / loading ----


def discover_modules_in(root: Path) -> list[ModuleHandle]:
    """Modules in one directory (`<root>/<name>/module.toml`). Bad manifests are skipped."""
    if not root.is_dir():
        return []
    out: list[ModuleHandle] = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        manifest_path = entry / _MANIFEST_FILENAME
        if not manifest_path.is_file():
            continue
        try:
            manifest = parse_manifest(manifest_path.read_text(encoding="utf-8"))
        except ManifestError as exc:
            print(f"warning: skipping module at {shown(entry)}: {shown(exc)}", file=sys.stderr)
            continue
        out.append(ModuleHandle(name=manifest.name, manifest=manifest, dir=entry))
    return out


def discover_modules(project: Project) -> list[ModuleHandle]:
    """Scan `<project>/.veles/modules/`."""
    return discover_modules_in(project.modules_dir)


def module_package(name: str) -> str:
    """The import name a loaded module's files live under — also the root of its
    loggers (`logging.getLogger(__name__)` in its files)."""
    return f"_veles_module_{name}"


def load_module(handle: ModuleHandle, registry: ModuleRegistry) -> None:
    """Import the entrypoint file and call `register(api)` to populate hooks."""
    try:
        file_path, func_part = entrypoint_file(handle.dir, handle.manifest.entrypoint)
    except ManifestError as exc:
        raise ModuleLoadError(str(exc)) from exc
    if not file_path.is_file():
        raise ModuleLoadError(f"entrypoint file {str(file_path)!r} not found")
    # The entrypoint is a package rooted at the module dir, so a multi-file module
    # imports its own files relatively (`from .helpers import x`).
    spec = importlib.util.spec_from_file_location(
        module_package(handle.name), file_path, submodule_search_locations=[str(handle.dir)]
    )
    if spec is None or spec.loader is None:
        raise ModuleLoadError(f"could not build import spec for {file_path}")
    module = importlib.util.module_from_spec(spec)
    # Standard importlib recipe: register in sys.modules before exec so
    # annotation resolution (e.g. `from __future__ import annotations` +
    # `dataclass(slots=True)`) can find the module via sys.modules[cls.__module__].
    # Removed again on any failure below so a failed module leaves nothing behind.
    sys.modules[spec.name] = module
    try:
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            raise ModuleLoadError(f"failed to import {file_path}: {exc}") from exc
        register = getattr(module, func_part, None)
        if not callable(register):
            raise ModuleLoadError(
                f"entrypoint {handle.manifest.entrypoint!r} resolved but is not callable"
            )
        scratch = ModuleRegistry()
        api = ModuleAPI(scratch, handle.name)
        try:
            register(api)
        except Exception as exc:
            raise ModuleLoadError(f"register() raised {type(exc).__name__}: {exc}") from exc
        try:
            refuse_builtin_collisions(scratch)
            registry.merge_from(scratch, handle.name)
            registry.module_dirs[handle.name] = handle.dir
        except ValueError as exc:
            raise ModuleLoadError(str(exc)) from exc
    except BaseException:
        for loaded in [m for m in sys.modules if m == spec.name or m.startswith(spec.name + ".")]:
            sys.modules.pop(loaded, None)
        raise


# ---- Hook firing ----


def fire_hook(hook_name: str, /, **ctx: Any) -> VetoResult | None:
    """Dispatch a hook by name to all registered modules.

    Each callback is wrapped in try/except so one misbehaving module
    cannot break the agent loop. `hook_name` is positional-only so
    callers can pass `name=` and other keys freely in `ctx`.

    Returns the first `VetoResult` produced by any callback (with
    `module_name` populated from the registered owner), or `None`. All
    callbacks run regardless of veto so observability hooks (logging,
    telemetry) still see the dispatch; only the caller of `fire_hook`
    for `pre_tool_call` consults the return value to cancel the tool.
    """
    reg = current_module_registry()
    if reg is None:
        return None
    veto: VetoResult | None = None
    for module_name, fn in reg.iter_hooks(hook_name):
        try:
            result = fn(ctx)
        except Exception as exc:
            print(
                f"warning: module {module_name!r} hook {hook_name!r} raised "
                f"{type(exc).__name__}: {shown(exc)}",
                file=sys.stderr,
            )
            continue
        if isinstance(result, VetoResult) and veto is None:
            veto = dataclasses.replace(result, module_name=module_name)
    return veto
