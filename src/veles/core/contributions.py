"""Typed contribution points — the one way a module adds to Veles.

A module's `register(api)` calls `api.contribute(point, name, obj)`; core reads
`contributions(point)` instead of importing the module's code. Each point is
declared here once (`register_point`), with the kind of object it accepts and
one consumer in core. A new point is one `register_point` call — the mechanism
itself never changes.

Builtin modules (`BUILTIN_MODULES`, shipped inside Veles) load lazily, once per
process, the first time anything asks for contributions, so every process — CLI,
daemon, the MCP child of a delegated CLI, a test calling core directly — sees
them whether or not its entry point loaded the user's modules. They are Veles'
own code, so they skip the approval gate user and project modules pass.
"""

from __future__ import annotations

import functools
import importlib
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from veles.core.text import shown

if TYPE_CHECKING:
    from veles.core.modules import ModuleRegistry
    from veles.core.project import Project


@dataclass(frozen=True, slots=True)
class Point:
    """`kind`: the type (or types) a contributed object must be an instance of;
    `None` accepts any callable. `keyed`: names are unique within the point."""

    name: str
    kind: type | tuple[type, ...] | None = None
    keyed: bool = True

    def accepts(self, obj: object) -> bool:
        return callable(obj) if self.kind is None else isinstance(obj, self.kind)


@dataclass(frozen=True, slots=True)
class Contribution:
    point: str
    name: str
    obj: object
    module: str


CONTRIBUTION_POINTS: dict[str, Point] = {}

BUILTIN_MODULES: tuple[str, ...] = (
    "veles.modules.wiki",
    "veles.modules.agentops",
    "veles.modules.organize",
)


def register_point(point: Point) -> None:
    CONTRIBUTION_POINTS[point.name] = point


def check(point: str, name: str, obj: object) -> Point:
    """The declared point for `point`, or `ValueError` saying why `obj` doesn't fit."""
    declared = CONTRIBUTION_POINTS.get(point)
    if declared is None:
        raise ValueError(f"unknown contribution point {point!r}")
    if not declared.accepts(obj):
        raise ValueError(f"{point}:{name}: {type(obj).__name__} is not what {point!r} takes")
    return declared


def contributions(point: str) -> list[Contribution]:
    """Every contribution to `point`: builtin modules, then the process's loaded modules."""
    from veles.core.modules import current_module_registry

    found = list(_builtin_registry().contributions(point))
    reg = current_module_registry()
    if reg is not None:
        found += reg.contributions(point)
    return found


_warned: set[tuple[str, str]] = set()


def call_each[T](point: str, fn: Callable[[Contribution], T]) -> list[T]:
    """`fn` applied to each contribution of `point`; one that raises is skipped with
    one warning per (point, module) per process — a broken module never breaks core."""
    out: list[T] = []
    for c in contributions(point):
        try:
            out.append(fn(c))
        except Exception as exc:
            key = (point, c.module)
            if key not in _warned:
                _warned.add(key)
                print(
                    f"warning: module {shown(c.module)} {point} {shown(c.name)!r} failed: "
                    f"{type(exc).__name__}: {shown(exc)}",
                    file=sys.stderr,
                )
    return out


@functools.cache
def _builtin_registry() -> ModuleRegistry:
    from veles.core.modules import ModuleAPI, ModuleRegistry

    registry = ModuleRegistry()
    for name in BUILTIN_MODULES:
        scratch = ModuleRegistry()
        try:
            importlib.import_module(name).register(ModuleAPI(scratch, name))
            registry.merge_from(scratch, name)
        except Exception as exc:
            print(
                f"warning: builtin module {name} did not load: {type(exc).__name__}: {shown(exc)}",
                file=sys.stderr,
            )
    return registry


def reset_builtin_contributions() -> None:
    """Forget the loaded builtins (tests swap `BUILTIN_MODULES`)."""
    _builtin_registry.cache_clear()
    _warned.clear()


@dataclass(frozen=True, slots=True)
class Engine:
    """A content engine (`[layout.engines] <name> = true` in a layout pack) that a
    module makes available — e.g. `wiki`."""

    name: str


# Every point is declared here, in one place: validate's `provides` check and the
# registry dry-run child must see all of them without importing their consumers.
register_point(Point("memory"))
register_point(Point("engine", kind=Engine))
# (project, query, *, limit) -> list[RecallHit] — consumer: core/memory/router.py
register_point(Point("recall"))


@dataclass(frozen=True, slots=True)
class ToolSet:
    """Agent tools a module owns. `load()` imports the code that registers them
    (`@tool`); `engine` gates them on a content engine the project's layout enables."""

    load: Callable[[], object]
    tools: tuple[str, ...]
    engine: str | None = None


register_point(Point("tool", kind=ToolSet))
# (project, *, include_index: bool) -> list[str] stable blocks — consumer: runtime/prompt.py
register_point(Point("prompt"))


@dataclass(frozen=True, slots=True)
class DreamStep:
    """A dream-cycle step a module owns. `run(project, result, *, dry_run)` fills its
    fields of the `DreamResult`; `skip_flag` names the `dream_cycle` keyword that
    skips it (e.g. `"skip_lint"`)."""

    name: str
    run: Callable[..., None]
    skip_flag: str


register_point(Point("dream_step", kind=DreamStep))


def load_tool_sets(project: Project | None) -> set[str]:
    """Load every contributed tool set the project can use; return the names of
    the tools it can't (sets whose engine its layout doesn't enable) so callers
    drop them from toolsets that list them."""
    from veles.core.layout.engines import engine_enabled

    gated: set[str] = set()

    def load(c: Contribution) -> None:
        ts = c.obj
        assert isinstance(ts, ToolSet)
        if ts.engine is not None and not engine_enabled(project, ts.engine):
            gated.update(ts.tools)
            return
        ts.load()

    call_each("tool", load)
    return gated


__all__ = [
    "BUILTIN_MODULES",
    "CONTRIBUTION_POINTS",
    "Contribution",
    "DreamStep",
    "Engine",
    "Point",
    "ToolSet",
    "call_each",
    "check",
    "contributions",
    "load_tool_sets",
    "register_point",
    "reset_builtin_contributions",
]
