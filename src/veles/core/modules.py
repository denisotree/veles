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

from veles.core.module_manifest import (
    ManifestError,
    ModuleManifest,
    parse_entrypoint,
    parse_manifest,
)
from veles.core.project import Project

_HOOK_NAMES: tuple[str, ...] = (
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


class ModuleRegistry:
    def __init__(self) -> None:
        self._hooks: dict[str, list[tuple[str, HookFn]]] = {n: [] for n in _HOOK_NAMES}
        self.modules: list[str] = []

    def add_hook(self, hook_name: str, module_name: str, fn: HookFn) -> None:
        if hook_name not in _HOOK_NAMES:
            raise ValueError(f"unknown hook {hook_name!r}; expected one of {_HOOK_NAMES}")
        self._hooks[hook_name].append((module_name, fn))

    def iter_hooks(self, hook_name: str) -> Iterator[tuple[str, HookFn]]:
        return iter(self._hooks.get(hook_name, []))


class ModuleAPI:
    """Thin facade passed to a module's `register(api)` function."""

    def __init__(self, registry: ModuleRegistry, module_name: str) -> None:
        self._registry = registry
        self._module_name = module_name

    def add_hook(self, hook_name: str, fn: HookFn) -> None:
        self._registry.add_hook(hook_name, self._module_name, fn)


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


def discover_modules(project: Project) -> list[ModuleHandle]:
    """Scan `<project>/.veles/modules/`. Skip directories with bad manifest."""
    root = project.modules_dir
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
            print(f"warning: skipping module at {entry}: {exc}", file=sys.stderr)
            continue
        out.append(ModuleHandle(name=manifest.name, manifest=manifest, dir=entry))
    return out


def load_module(handle: ModuleHandle, registry: ModuleRegistry) -> None:
    """Import the entrypoint file and call `register(api)` to populate hooks."""
    file_part, func_part = parse_entrypoint(handle.manifest.entrypoint)
    file_path = handle.dir / file_part
    if not file_path.is_file():
        raise ModuleLoadError(f"entrypoint file {file_part!r} not found in {handle.dir}")
    spec = importlib.util.spec_from_file_location(f"_veles_module_{handle.name}", file_path)
    if spec is None or spec.loader is None:
        raise ModuleLoadError(f"could not build import spec for {file_path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise ModuleLoadError(f"failed to import {file_path}: {exc}") from exc
    register = getattr(module, func_part, None)
    if not callable(register):
        raise ModuleLoadError(
            f"entrypoint {handle.manifest.entrypoint!r} resolved but is not callable"
        )
    api = ModuleAPI(registry, handle.name)
    try:
        register(api)
    except Exception as exc:
        raise ModuleLoadError(f"register() raised {type(exc).__name__}: {exc}") from exc
    registry.modules.append(handle.name)


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
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            continue
        if isinstance(result, VetoResult) and veto is None:
            veto = dataclasses.replace(result, module_name=module_name)
    return veto
