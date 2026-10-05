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
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from veles.core.platforms import PlatformSpec
from veles.core.text import shown

if TYPE_CHECKING:
    from veles.core.modules import ModuleRegistry
    from veles.core.project import Project


@dataclass(frozen=True, slots=True)
class Point:
    """`kind`: the type (or types) a contributed object must be an instance of;
    `None` accepts any callable. `keyed`: names are unique within the point.
    `reserved`: names core already uses for its own entries in the consumer.
    `key`: the identity a consumer keys on (e.g. a `BackgroundOp`'s `kind`) —
    it must equal the contributed name, so name uniqueness covers it."""

    name: str
    kind: type | tuple[type, ...] | None = None
    keyed: bool = True
    reserved: frozenset[str] = frozenset()
    key: Callable[[object], str] | None = None

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
    if name in declared.reserved:
        raise ValueError(f"{point}:{name}: the name is reserved by core")
    if declared.key is not None and declared.key(obj) != name:
        raise ValueError(f"{point}:{name}: the name must equal its kind {declared.key(obj)!r}")
    return declared


def refuse_builtin_collisions(registry: ModuleRegistry) -> None:
    """`ValueError` when a user/project module's contribution takes a name a builtin
    module already uses — a module never silently replaces Veles' own."""
    builtin = _builtin_registry()
    for point in CONTRIBUTION_POINTS:
        for c in registry.contributions(point):
            builtin._refuse_taken(point, c.name)


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
    return _call(point, contributions(point), fn)


def call_active[T](project: Project | None, point: str, fn: Callable[[Contribution], T]) -> list[T]:
    """`call_each` over the contributions whose engine the project enables (`active`)."""
    return _call(point, active(project, point), fn)


def _call[T](point: str, found: list[Contribution], fn: Callable[[Contribution], T]) -> list[T]:
    out: list[T] = []
    for c in found:
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


_builtin_lock = threading.RLock()


def _builtin_registry() -> ModuleRegistry:
    # Daemon worker threads can ask first at the same moment; the builtins load once.
    with _builtin_lock:
        return _load_builtins()


@functools.cache
def _load_builtins() -> ModuleRegistry:
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
    _load_builtins.cache_clear()
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
# A messaging platform the daemon hosts as a channel — consumer: core/platforms.py
register_point(Point("platform", kind=PlatformSpec))
# (project, query, *, limit) -> list[RecallHit] — consumer: core/memory/router.py
register_point(Point("recall", reserved=frozenset({"insights", "turns", "about", "extra"})))


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


register_point(Point("dream_step", kind=DreamStep, key=lambda s: s.name))  # type: ignore[attr-defined]


@dataclass(frozen=True, slots=True)
class CuratorTarget:
    """Where the curator's agent persists a distilled session when `engine` is on.
    `prepare(project)` readies the store; `instructions(project, session_id)` returns
    `(intro, persist_steps, log_step)` prompt text; `persist_tools` are the tools whose
    use means the distillation persisted."""

    engine: str
    prepare: Callable[..., None]
    instructions: Callable[..., tuple[str, str, str]]
    persist_tools: tuple[str, ...]


register_point(Point("curator_target", kind=CuratorTarget))


class PageInfo(Protocol):
    """A page a module exposes to core heuristics (subproject clustering)."""

    rel_path: str
    title: str
    summary: str
    category: str


@dataclass(frozen=True, slots=True)
class PageSource:
    """`pages(project)` — a module's pages for subproject clustering, when `engine`
    (if any) is on for the project."""

    pages: Callable[..., list[PageInfo]]
    engine: str | None = None


register_point(Point("subproject_source", kind=PageSource))


@dataclass(frozen=True, slots=True)
class PageStore:
    """A module that keeps pages. `write(project, category, slug, title, content)`
    returns the project-relative path (raises `ValueError` on a bad slug);
    `read(project, category, slug)` returns the page text or None. Active when
    `engine` (if any) is on for the project."""

    write: Callable[..., str]
    read: Callable[..., str | None]
    engine: str | None = None


# — consumers: core/self_doc.py (category "self-doc"), the REPL's /save and
#   `veles self-doc show`
register_point(Point("page_store", kind=PageStore))


def page_store(project: Project | None) -> PageStore | None:
    """The project's active page store — the first one, when several are."""
    found = active(project, "page_store")
    return found[0].obj if found else None  # type: ignore[return-value]


# (root: Path, manifest: LayoutManifest) -> None, for every applied pack
# — consumer: core/layout/scaffold.py
register_point(Point("scaffold"))


@dataclass(frozen=True, slots=True)
class BackgroundOp:
    """A daemon job kind a module owns. `run(job, *, spawn_agent, project) -> str`
    does the work; `spawn_agent(system_prompt)` builds a sub-agent capped to the
    `toolset` named here (e.g. `"ingest"`). Returns the job's summary text."""

    kind: str
    toolset: str
    run: Callable[..., str]


register_point(
    Point("background_op", kind=BackgroundOp, key=lambda op: op.kind)  # type: ignore[attr-defined]
)


@dataclass(frozen=True, slots=True)
class SlashReply:
    """What a module's slash command answers: `text` to show; `submit_prompt`, when
    set, runs as the next agent turn; `error` marks the text as an error."""

    text: str = ""
    submit_prompt: str | None = None
    error: bool = False


@dataclass(frozen=True, slots=True)
class SlashCommand:
    """A REPL command `/<contribution name>`: `run(project, arg) -> SlashReply`.
    Shown only where `engine` (if any) is on; builtin command names stay builtin."""

    run: Callable[..., SlashReply]
    summary: str = ""
    usage: str = ""
    engine: str | None = None


# — consumer: cli/repl/slash/builtin.py (build_default_registry)
register_point(Point("slash_command", kind=SlashCommand))


class CommandHost(Protocol):
    """What the CLI does for a module's command: `run_agent` builds an agent the
    way `veles run` does (provider, key check, the project's run system prompt for
    `prompt_hint`, the given `tools`), runs `message` as one turn — a callable is
    called only once the provider is ready — and returns the exit code."""

    def run_agent(
        self,
        message: str | Callable[[], str],
        *,
        tools: tuple[str, ...],
        prompt_hint: str,
        fallback_prompt: str = "",
    ) -> int: ...


@dataclass(frozen=True, slots=True)
class CliCommand:
    """A `veles <contribution name>` verb: `add_arguments(parser)` declares its
    arguments; `run(args, project, host: CommandHost) -> int` runs it inside the
    project. `run_flags` adds the shared agent flags (`--provider`, `--model`, …).
    Builtin verb names stay builtin."""

    help: str
    add_arguments: Callable[..., None]
    run: Callable[..., int]
    run_flags: bool = False


# — consumer: cli/__init__.py + cli/module_commands.py
register_point(Point("cli_command", kind=CliCommand))


def active(project: Project | None, point: str) -> list[Contribution]:
    """Contributions to `point` whose `engine` (if the object has one) is enabled."""
    from veles.core.layout.engines import engine_enabled

    out: list[Contribution] = []
    for c in contributions(point):
        engine = getattr(c.obj, "engine", None)
        if engine is None or engine_enabled(project, engine):
            out.append(c)
    return out


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
    "BackgroundOp",
    "CliCommand",
    "CommandHost",
    "Contribution",
    "CuratorTarget",
    "DreamStep",
    "Engine",
    "PageInfo",
    "PageSource",
    "PageStore",
    "Point",
    "SlashCommand",
    "SlashReply",
    "ToolSet",
    "active",
    "call_active",
    "call_each",
    "check",
    "contributions",
    "load_tool_sets",
    "page_store",
    "refuse_builtin_collisions",
    "register_point",
    "reset_builtin_contributions",
]
