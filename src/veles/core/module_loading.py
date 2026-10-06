"""Load a project's modules — every process that runs an agent calls this (the CLI,
the daemon, the delegated-CLI MCP child), so a registry-installed module exists
wherever the agent works.

User-level modules (`~/.veles/modules/`) come first, then the project's. Each
passes the load gate first; only then does an approved project module replace a
same-named user-level one, so an unapproved dir can never disable an approved
module. Problems are warnings on stderr — never stdout, which the MCP child uses
for protocol frames.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from veles.core.modules import (
    ModuleHandle,
    ModuleLoadError,
    ModuleRegistry,
    discover_modules,
    discover_modules_in,
    load_module,
)
from veles.core.text import shown

if TYPE_CHECKING:
    from veles.core.project import Project


def load_user_modules(into: ModuleRegistry | None = None) -> ModuleRegistry:
    """The user-level modules only (`~/.veles/modules/`) — for commands that run
    without a project (`veles channel`). With `into`, only those not loaded there
    yet are added to it."""
    from veles.core.user_paths import user_modules_dir

    handles = _dedup_by_name(
        _admitted(discover_modules_in(user_modules_dir()), project_root=None), scope="user"
    )
    return _load_handles(handles, into)


def _load_handles(handles: list[ModuleHandle], into: ModuleRegistry | None) -> ModuleRegistry:
    registry = into if into is not None else ModuleRegistry()
    loaded = set(registry.modules)
    for handle in handles:
        if handle.name in loaded:
            continue
        try:
            load_module(handle, registry)
        except ModuleLoadError as exc:
            _warn(f"skipping module {handle.name!r}: {shown(exc)}")
    return registry


def load_project_modules(project: Project, into: ModuleRegistry | None = None) -> ModuleRegistry:
    """The project's modules in a new registry — or, with `into` (after an install
    mid-session), only the modules not already loaded there, added to it: an
    entrypoint never runs twice in one process."""
    from veles.core.user_paths import user_modules_dir

    project_handles = _dedup_by_name(
        _admitted(discover_modules(project), project_root=project.root), scope="project"
    )
    overridden = {h.name for h in project_handles}
    user_handles = _dedup_by_name(
        _admitted(discover_modules_in(user_modules_dir()), project_root=None), scope="user"
    )
    handles: list[ModuleHandle] = []
    for h in user_handles:
        if h.name in overridden:
            _warn(f"module {h.name!r} in the project overrides the user-level one")
            continue
        handles.append(h)
    handles.extend(project_handles)
    return _load_handles(handles, into)


def _warn(message: str) -> None:
    print(f"warning: {message}", file=sys.stderr)


def _dedup_by_name(handles: list[ModuleHandle], *, scope: str) -> list[ModuleHandle]:
    """Two module dirs in the same scope sharing a manifest `name`: keep only the
    first (sorted by dir — `discover_modules_in` already sorts) and warn about the rest."""
    seen: dict[str, ModuleHandle] = {}
    out: list[ModuleHandle] = []
    for h in handles:
        if h.name in seen:
            _warn(
                f"duplicate {scope} module name {h.name!r} at {shown(h.dir)} "
                f"(already loading from {shown(seen[h.name].dir)}) — ignored"
            )
            continue
        seen[h.name] = h
        out.append(h)
    return out


def _admitted(handles: list[ModuleHandle], *, project_root: Path | None) -> list[ModuleHandle]:
    """The handles the load gate admits in this scope (`project_root` None = user);
    each refused one is named by its dir."""
    from veles.core.registry.gate import admit_module

    out: list[ModuleHandle] = []
    for handle in handles:
        refusal = admit_module(handle.dir, project_root=project_root)
        if refusal is None:
            out.append(handle)
            continue
        _warn(
            f"skipping module {handle.name!r} at {shown(handle.dir)}: {shown(refusal)} — "
            f"review it, then `{_approve_command(handle.name, project_root)}`"
        )
    return out


def refused_modules(project: Project | None) -> list[tuple[str, str, str]]:
    """`(name, why, approve command)` for each module on disk the load gate refuses, in
    the user scope and the project's — `veles doctor` reports them; loading only warns."""
    from veles.core.registry.gate import admit_module
    from veles.core.user_paths import user_modules_dir

    scopes: list[tuple[list[ModuleHandle], Path | None]] = [
        (discover_modules_in(user_modules_dir()), None)
    ]
    if project is not None:
        scopes.append((discover_modules(project), project.root))
    out: list[tuple[str, str, str]] = []
    for handles, root in scopes:
        for handle in handles:
            refusal = admit_module(handle.dir, project_root=root)
            if refusal is not None:
                out.append((handle.name, refusal, _approve_command(handle.name, root)))
    return out


def _approve_command(name: str, project_root: Path | None) -> str:
    return f"veles module approve {'--user ' if project_root is None else ''}{name}"


__all__ = ["load_project_modules", "load_user_modules", "refused_modules"]
