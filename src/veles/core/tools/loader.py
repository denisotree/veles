"""M120.2: load Python tool modules from `<cwd>/.veles/tools/` and
`~/.veles/tools/` into a `Registry`.

VISION §5.4 contract: tools are accumulating capability. Builtin tools
self-register via `@tool` at import time; this loader adds the two
file-based origins:

- **project-level** `<project>/.veles/tools/*.py` — `scope="project"`,
  shadows user-level tools of the same name (project override).
- **user-level**  `~/.veles/tools/*.py`           — `scope="user"`,
  shadows builtin tools (rare but allowed for hotfixes).

Each `.py` file is imported via importlib so its `@tool`-decorated
functions register into a fresh isolated registry. Imports are sequenced
so that name collisions resolve to the higher-priority scope (project >
user > builtin); a collision is reported as a `LoaderWarning` carrying
the shadowed name's scope so the agent log isn't silent about
overrides.

This module does **not** generate code, sandbox imports, or call the
LLM. Those concerns belong to M120b (`tool_authoring` skill +
`tool_installer` skill). Here we just *load* what's already on disk —
a thin parallel to `core/skills.py::discover_skills`.
"""

from __future__ import annotations

import importlib.util
import logging
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

from veles.core.tools.persistence import upsert_tool
from veles.core.tools.registry import Registry, ToolEntry

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LoadedTool:
    """One tool that came off disk. `entry` is the same object the
    Registry holds (handler, schema, side-effects); `scope` and
    `origin` are the metadata the catalogue persists to memory.db."""

    entry: ToolEntry
    scope: str  # "project" | "user"
    origin: str  # "agent-generated" | "manual"
    source: Path  # the .py file the tool came from


@dataclass(frozen=True, slots=True)
class LoadReport:
    """Summary of one `load_into_registry` call. Useful for logging
    and tests."""

    loaded: tuple[LoadedTool, ...] = ()
    overridden: tuple[tuple[str, str], ...] = ()
    # name, error string for files that failed to import
    errors: tuple[tuple[str, str], ...] = ()


# ---------- public API ----------


def load_into_registry(
    registry: Registry,
    *,
    project_tools_dir: Path | None = None,
    user_tools_dir: Path | None = None,
    conn: sqlite3.Connection | None = None,
) -> LoadReport:
    """Discover and import every `.py` under `project_tools_dir` and
    `user_tools_dir`, register their `@tool` functions into `registry`,
    and (when `conn` is given) sync each loaded tool into the
    `tools` table.

    Resolution order, highest priority first:
      1. project tools  (`scope="project"`)
      2. user tools     (`scope="user"`)
      3. anything `registry` already had  (`scope="builtin"`)

    The caller hands in a pre-populated `Registry` (typically with
    builtins via `@tool`); this function only *adds* to it. When a
    project tool shadows a builtin, the loader removes the builtin
    entry from the registry first so the project version wins.
    """
    loaded: list[LoadedTool] = []
    overridden: list[tuple[str, str]] = []
    errors: list[tuple[str, str]] = []

    # `claimed[name] = scope` — which file-based scope already owns the
    # name. Used to disambiguate "duplicate in same scope" (record the
    # losing scope) from "shadowed by higher-priority scope" (record
    # the winning scope).
    claimed: dict[str, str] = {}

    project_files = _list_python_files(project_tools_dir)
    user_files = _list_python_files(user_tools_dir)

    for source in project_files:
        result = _load_one_file(
            source,
            registry=registry,
            scope="project",
            origin="agent-generated",
            claimed=claimed,
            overridden=overridden,
        )
        if isinstance(result, str):
            errors.append((source.name, result))
            continue
        loaded.extend(result)
        for lt in result:
            claimed[lt.entry.name] = "project"

    for source in user_files:
        result = _load_one_file(
            source,
            registry=registry,
            scope="user",
            origin="manual",
            claimed=claimed,
            overridden=overridden,
        )
        if isinstance(result, str):
            errors.append((source.name, result))
            continue
        loaded.extend(result)
        for lt in result:
            claimed[lt.entry.name] = "user"

    # Persist whatever we just loaded (or refreshed).
    if conn is not None:
        for lt in loaded:
            upsert_tool(
                conn, lt.entry, scope=lt.scope, origin=lt.origin
            )

    return LoadReport(
        loaded=tuple(loaded),
        overridden=tuple(overridden),
        errors=tuple(errors),
    )


# ---------- internals ----------


def _list_python_files(directory: Path | None) -> list[Path]:
    if directory is None or not directory.is_dir():
        return []
    return sorted(
        p
        for p in directory.iterdir()
        if p.is_file() and p.suffix == ".py" and not p.name.startswith("_")
    )


def _load_one_file(
    source: Path,
    *,
    registry: Registry,
    scope: str,
    origin: str,
    claimed: dict[str, str],
    overridden: list[tuple[str, str]],
) -> list[LoadedTool] | str:
    """Import `source`, capture every newly-registered tool, attach
    them to `registry` under the right scope. Returns either a list of
    loaded tools or an error string for the import failure."""
    # Use a unique module name per file so re-imports don't share state
    # across `load_into_registry` calls in tests.
    mod_name = f"veles_user_tools_{scope}_{source.stem}_{id(source)}"

    # Compose a sandbox registry: tools inside `source` register here,
    # not into the global `core.tools.registry::registry`. This keeps
    # builtins immune to a `@tool(name="read_file")` collision dropped
    # into a user file.
    sandbox = Registry()

    # Patch the global registry used by `@tool` decorator while the
    # module imports. `core/tools/__init__.py` re-exports the `registry`
    # instance under the same dotted name as the module, so the normal
    # `import veles.core.tools.registry as ...` would resolve to the
    # instance. Pull the actual module out of `sys.modules` instead.
    _registry_module = sys.modules["veles.core.tools.registry"]
    saved_registry = _registry_module.registry
    _registry_module.registry = sandbox

    try:
        spec = importlib.util.spec_from_file_location(mod_name, source)
        if spec is None or spec.loader is None:
            return f"cannot build import spec"
        module = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException as exc:  # noqa: BLE001
            sys.modules.pop(mod_name, None)
            logger.warning(
                "tools loader: failed to import %s: %s", source, exc
            )
            return f"{type(exc).__name__}: {exc}"
    finally:
        _registry_module.registry = saved_registry

    # Anything that registered in the sandbox is now ours to merge.
    # `overridden` carries `(name, winning_scope)` so the agent log
    # can say "your user-level `echo` was shadowed by the project one".
    out: list[LoadedTool] = []
    for entry_name in sandbox.list_names():
        entry = sandbox.get(entry_name)
        prior_scope = claimed.get(entry_name)
        if prior_scope == scope:
            # Same-scope duplicate (two project files both define `x`).
            # First file wins; record the losing scope.
            overridden.append((entry_name, scope))
            continue
        if prior_scope is not None:
            # Cross-scope: a higher-priority scope already claimed the
            # name. We're the loser; record the winner's scope so log
            # messages can say "project overrode this".
            overridden.append((entry_name, prior_scope))
            continue
        # Nothing on disk has claimed this name yet. If a builtin
        # already holds it (via @tool import-time registration), the
        # file-based scope wins by VISION §5.4's project/user override
        # rule — drop the builtin and record the displacement.
        if entry_name in registry.list_names():
            registry._tools.pop(entry_name, None)
            overridden.append((entry_name, scope))
        registry.register(entry)
        out.append(
            LoadedTool(entry=entry, scope=scope, origin=origin, source=source)
        )
    return out


__all__ = [
    "LoadedTool",
    "LoadReport",
    "load_into_registry",
]
