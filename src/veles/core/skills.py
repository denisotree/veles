"""Skills — per-project parametrized sub-agents.

A skill is a directory under `<project>/.veles/skills/<name>/` containing a
`SKILL.md` file. The frontmatter declares the skill's identity and tool budget;
the body is the system prompt for a disposable sub-agent.

When the top-level agent calls a skill (it appears as a registered tool with a
single `input: str` parameter), Veles spawns a fresh `Agent` whose
`system_prompt` is the skill body and whose registry is the parent's builtin
tools filtered to `skill.tools`. The sub-agent runs to completion; its final
text becomes the tool result.

Use_count and last_used live in the same SKILL.md frontmatter and are bumped
atomically (temp-file + replace) after each successful invocation.

The frontmatter parser is intentionally a flat-key subset of YAML — strings,
ints, bools, null, simple lists. No external dependency, no nested structures.
M6 can swap to pyyaml if real YAML is required.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

from veles.core.file_lock import file_lock
from veles.core.tools.registry import Registry, ToolEntry

if TYPE_CHECKING:
    from collections.abc import Callable

    from veles.core.project import Project
    from veles.core.provider import Provider


_SKILL_FILENAME = "SKILL.md"
_DEFAULT_TOOLS: list[str] = []
_DEFAULT_MAX_ITERATIONS = 10
_MAX_SKILL_DEPTH = 5


@dataclass(slots=True)
class Skill:
    name: str
    description: str
    body: str
    path: Path
    tools: list[str] = field(default_factory=list)
    max_iterations: int = _DEFAULT_MAX_ITERATIONS
    use_count: int = 0
    last_used: str | None = None
    parameters: list[dict[str, Any]] = field(default_factory=list)
    success_count: int = 0
    error_count: int = 0
    last_error_at: str | None = None
    scope: str = "project"  # "project" | "user"; M40 user-level skills
    # M121: name of a base skill this one extends. Runtime resolver
    # (`resolve_inheritance`) walks the chain so a child skill can
    # delegate to its parent's tools/parameters/body without copying.
    extends: str | None = None


# ---------- frontmatter parser ----------


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Return (frontmatter_dict, body). Returns ({}, text) if no frontmatter.

    Supports flat key-value pairs plus a single nesting level: a top-level key
    whose value is empty opens a list-of-dicts context; subsequent indented
    `- key: value` lines become list items (each a dict), and further indented
    `key: value` lines fill the most recent dict.
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text
    fm: dict[str, Any] = {}
    body_start: int | None = None
    current_list_key: str | None = None
    current_dict: dict[str, Any] | None = None

    for i in range(1, len(lines)):
        raw_line = lines[i]
        if raw_line.strip() == "---":
            body_start = i + 1
            break
        stripped_full = raw_line.strip()
        if not stripped_full:
            continue
        indent = len(raw_line) - len(raw_line.lstrip())
        stripped = raw_line.lstrip()

        if indent == 0:
            current_list_key = None
            current_dict = None
            if ":" not in stripped:
                continue
            key, _, raw_val = stripped.partition(":")
            key = key.strip()
            raw_val = raw_val.strip()
            if not raw_val:
                # Open a list-of-dicts context for the next indented lines.
                current_list_key = key
                fm[key] = []
                continue
            fm[key] = _coerce_value(raw_val)
            continue

        if current_list_key is None:
            continue
        if stripped.startswith("- "):
            current_dict = {}
            fm[current_list_key].append(current_dict)
            rest = stripped[2:].strip()
            if rest and ":" in rest:
                k, _, v = rest.partition(":")
                current_dict[k.strip()] = _coerce_value(v.strip())
        elif current_dict is not None and ":" in stripped:
            k, _, v = stripped.partition(":")
            current_dict[k.strip()] = _coerce_value(v.strip())

    if body_start is None:
        return {}, text
    body = "\n".join(lines[body_start:]).lstrip("\n")
    return fm, body


def render_frontmatter(fm: dict[str, Any], body: str) -> str:
    """Return canonical SKILL.md text with `---`-delimited frontmatter.

    Lists-of-dicts render as YAML-ish indented blocks; everything else stays
    on one line.
    """
    out = ["---"]
    for key, value in fm.items():
        if isinstance(value, list) and value and all(isinstance(v, dict) for v in value):
            out.append(f"{key}:")
            for item in value:
                first = True
                for k, v in item.items():
                    prefix = "  - " if first else "    "
                    out.append(f"{prefix}{k}: {_format_value(v)}")
                    first = False
            continue
        out.append(f"{key}: {_format_value(value)}")
    out.append("---")
    out.append("")
    out.append(body.lstrip("\n"))
    return "\n".join(out)


def _coerce_value(raw: str) -> Any:
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1]
        items = [item.strip() for item in inner.split(",") if item.strip()]
        return [_coerce_scalar(it) for it in items]
    return _coerce_scalar(raw)


def _coerce_scalar(raw: str) -> Any:
    s = raw.strip()
    if not s:
        return ""
    lower = s.lower()
    if lower == "null":
        return None
    if lower in ("true", "false"):
        return lower == "true"
    if s.lstrip("-").isdigit():
        return int(s)
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    return s


def _format_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return "[" + ", ".join(_format_value(v) for v in value) + "]"
    return str(value)


# ---------- discovery ----------


def user_skills_dir() -> Path:
    """User-global skills directory. `VELES_USER_HOME` env overrides `~`.

    M40 introduces `~/.veles/skills/` as a peer of the project-local
    `<project>/.veles/skills/`. On name collision project wins; see
    `discover_skills`.
    """
    from veles.core.user_paths import user_skills_dir as _path

    return _path()


# M158-followup: optional TTL memo for `discover_skills` (daemon-only — see
# its docstring). Keyed on (project root, include_layout, resolve_inheritance);
# guarded by a lock because the daemon builds agents on `asyncio.to_thread`
# workers, so concurrent turns can call in parallel.
_SKILLS_CACHE: dict[tuple[str, bool, bool], tuple[list[Skill], float]] = {}
_SKILLS_CACHE_LOCK = threading.Lock()


def discover_skills(
    project: Project,
    *,
    include_layout: bool = False,
    resolve_inheritance_chain: bool = True,
    cache_ttl: float | None = None,
) -> list[Skill]:
    """Walk project + user skill dirs, plus the active layout-pack's
    `skills/` (when `include_layout=True`). Project takes precedence
    on name collisions.

    Resolution order, highest priority first:
      1. `<project>/.veles/skills/`           (scope = "project")
      2. `~/.veles/skills/`                   (scope = "user")
      3. Active layout-pack's `skills/`       (scope = "builtin", M117b)

    The `include_layout` toggle defaults False to preserve the M40 era
    contract (discover_skills returns only on-disk user-or-project
    skills). Runtime call sites that build the agent's tool surface
    (`cli/_runtime.py::_load_skills`, daemon factory) pass
    `include_layout=True` so the pack-shipped `ingest` / `query` /
    `lint` skills materialise as callable tools. Tests that pre-date
    M117b can keep the default and continue to see an empty list on
    a fresh project.

    M121c: when `resolve_inheritance_chain=True` (the default), every
    skill with a non-empty `extends` field is collapsed via
    `skills_persistence.resolve_inheritance` before being returned.
    The agent then dispatches a child skill against its flattened
    contract — child's body, base's tools, etc. Tests that want to
    inspect the raw on-disk skill (e.g. assert `extends` survived the
    parser) pass `resolve_inheritance_chain=False`.

    M158-followup: `cache_ttl` (seconds) memoises the discovered list per
    `(project, flags)` for that long. Default `None` = no cache: every call
    re-reads on-disk truth, so CLI one-shots and tests see a freshly-authored
    skill immediately. The long-lived daemon passes a few-minute TTL (config
    `[daemon] skills_cache_ttl`, default 600s) so it stops re-parsing every
    `SKILL.md` on every turn; the trade is that a skill the agent authors at
    runtime becomes callable within ≤TTL rather than on the very next turn.
    A returned list is always a fresh copy — callers may mutate it freely.
    """
    if cache_ttl is None or cache_ttl <= 0:
        return _discover_skills_uncached(
            project,
            include_layout=include_layout,
            resolve_inheritance_chain=resolve_inheritance_chain,
        )
    key = (str(project.root), include_layout, resolve_inheritance_chain)
    now = time.monotonic()
    with _SKILLS_CACHE_LOCK:
        hit = _SKILLS_CACHE.get(key)
        if hit is not None and now < hit[1]:
            return list(hit[0])
    merged = _discover_skills_uncached(
        project,
        include_layout=include_layout,
        resolve_inheritance_chain=resolve_inheritance_chain,
    )
    with _SKILLS_CACHE_LOCK:
        _SKILLS_CACHE[key] = (merged, time.monotonic() + cache_ttl)
    return list(merged)


def _discover_skills_uncached(
    project: Project,
    *,
    include_layout: bool,
    resolve_inheritance_chain: bool,
) -> list[Skill]:
    """The disk walk + merge + inheritance resolution behind
    `discover_skills` — split out so the TTL memo wraps a pure recompute."""
    project_skills = _discover_in_dir(project.skills_dir, scope="project")
    user_skills = _discover_in_dir(user_skills_dir(), scope="user")
    seen = {s.name for s in project_skills}
    merged = list(project_skills)
    for s in user_skills:
        if s.name in seen:
            continue
        merged.append(s)
        seen.add(s.name)
    if include_layout:
        for s in mount_layout_skills(project):
            if s.name in seen:
                continue
            merged.append(s)
            seen.add(s.name)
        # M120b: builtin Veles skills (tool_authoring, tool_installer)
        # mount alongside the layout-pack so they're available
        # regardless of which layout the project picked. They're at
        # the same lowest priority — project/user overrides win.
        for s in mount_builtin_skills():
            if s.name in seen:
                continue
            merged.append(s)
            seen.add(s.name)
    if resolve_inheritance_chain and any(s.extends for s in merged):
        from veles.core.skills_persistence import resolve_inheritance

        by_name = {s.name: s for s in merged}
        merged = [resolve_inheritance(s, by_name) for s in merged]
    return merged


def mount_layout_skills(project: Project) -> list[Skill]:
    """Discover skills the active layout-pack ships under its
    `skills/<name>/SKILL.md` directory tree. Empty list when the
    project's `layout_name` doesn't resolve to a known pack.

    The pack is found via `core.layout.discovery.find_layout`; the
    pack's `root / "skills"` is walked with the same loader the
    project/user paths use, so frontmatter validation is uniform.
    """
    from veles.core.layout.discovery import find_layout

    pack = find_layout(project.layout_name, project=project)
    if pack is None:
        return []
    return _discover_in_dir(pack.root / "skills", scope="builtin")


def mount_builtin_skills() -> list[Skill]:
    """Discover the system skills bundled with Veles itself —
    `tool_authoring`, `tool_installer`, etc. (M120b). These live under
    `src/veles/builtin_skills/` and aren't tied to a project layout,
    so they're discoverable regardless of which layout-pack a project
    is using.

    Returns an empty list when the directory isn't present (defensive
    against a partial install)."""
    builtin_root = Path(__file__).resolve().parent.parent / "builtin_skills"
    if not builtin_root.is_dir():
        return []
    return _discover_in_dir(builtin_root, scope="builtin")


def _discover_in_dir(skills_dir: Path, *, scope: str) -> list[Skill]:
    if not skills_dir.is_dir():
        return []
    out: list[Skill] = []
    for entry in sorted(skills_dir.iterdir()):
        if not entry.is_dir():
            continue
        skill_path = entry / _SKILL_FILENAME
        if not skill_path.is_file():
            continue
        skill = _load_skill(skill_path, scope=scope)
        if skill is None:
            continue
        out.append(skill)
    return out


def _typed_or_default(fm: dict[str, Any], key: str, py_type: type, default: Any) -> Any:
    """Return `fm[key]` when its runtime type matches `py_type`, else `default`.

    Skill frontmatter is hand-written YAML-ish; any field can be missing or the
    wrong type. Rather than crash on a single bad value we silently fall back
    so the rest of the skill keeps working. Warnings for hard requirements
    (`name`, `description`) are emitted at the call site.
    """
    value = fm.get(key, default)
    return value if isinstance(value, py_type) else default


def _load_skill(skill_path: Path, *, scope: str = "project") -> Skill | None:
    raw = skill_path.read_text(encoding="utf-8", errors="replace")
    fm, body = parse_frontmatter(raw)

    name = fm.get("name") or skill_path.parent.name
    if not isinstance(name, str) or not name:
        logger.warning("skipping skill at %s: missing 'name'", skill_path)
        return None
    description = fm.get("description")
    if not isinstance(description, str) or not description:
        logger.warning("skipping skill %r: missing 'description'", name)
        return None

    tools_raw = fm.get("tools")
    if tools_raw is not None and not isinstance(tools_raw, list):
        logger.warning(
            "skill %r: 'tools' must be a list, got %s",
            name,
            type(tools_raw).__name__,
        )
        tools_raw = None
    tools = [str(t) for t in (tools_raw or _DEFAULT_TOOLS)]

    parameters = [
        p for p in _typed_or_default(fm, "parameters", list, []) if isinstance(p, dict)
    ]

    extends_raw = fm.get("extends")
    extends_value = extends_raw if isinstance(extends_raw, str) and extends_raw.strip() else None

    return Skill(
        name=name,
        description=description,
        body=body,
        path=skill_path,
        tools=tools,
        max_iterations=_typed_or_default(fm, "max_iterations", int, _DEFAULT_MAX_ITERATIONS),
        use_count=_typed_or_default(fm, "use_count", int, 0),
        last_used=_typed_or_default(fm, "last_used", str, None),
        parameters=parameters,
        success_count=_typed_or_default(fm, "success_count", int, 0),
        error_count=_typed_or_default(fm, "error_count", int, 0),
        last_error_at=_typed_or_default(fm, "last_error_at", str, None),
        scope=scope,
        extends=extends_value.strip() if extends_value else None,
    )


# ---------- telemetry write-back ----------


def bump_telemetry(skill: Skill, *, success: bool) -> None:
    """Atomically bump use_count + outcome counter in SKILL.md.

    `use_count` counts every invocation; `success_count` increments only on
    `stopped_reason == "completed"`, `error_count` on exception or any
    non-completed terminal state. Future curator (M28) ranks duplicates
    by the derived `success_rate = success_count / use_count`.

    Concurrent invocations from the parent process and one or more MCP
    children can race on this read-modify-write — a sidecar flock at
    `<SKILL.md>.lock` serialises every bumper across threads and
    processes (M30).
    """
    lock_path = skill.path.with_suffix(skill.path.suffix + ".lock")
    with file_lock(lock_path):
        raw = skill.path.read_text(encoding="utf-8", errors="replace")
        fm, body = parse_frontmatter(raw)
        if not fm:
            return  # malformed file — leave alone
        now_iso = _dt.datetime.now(tz=_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        new_use = int(fm.get("use_count", 0) or 0) + 1
        fm["use_count"] = new_use
        fm["last_used"] = now_iso
        if success:
            fm["success_count"] = int(fm.get("success_count", 0) or 0) + 1
        else:
            fm["error_count"] = int(fm.get("error_count", 0) or 0) + 1
            fm["last_error_at"] = now_iso
        text = render_frontmatter(fm, body)
        tmp = skill.path.with_suffix(skill.path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(skill.path)
    skill.use_count = new_use
    skill.last_used = fm["last_used"]
    skill.success_count = int(fm.get("success_count", 0) or 0)
    skill.error_count = int(fm.get("error_count", 0) or 0)
    last_err = fm.get("last_error_at")
    skill.last_error_at = last_err if isinstance(last_err, str) else skill.last_error_at


# ---------- tool factory ----------


def make_skill_tool(
    skill: Skill,
    *,
    provider: Provider,
    model: str,
    base_registry: Registry,
) -> ToolEntry:
    """Build a ToolEntry that, when invoked, runs the skill as a sub-agent.

    `base_registry` is the registry the skill's sub-agent will subset its tools
    from. Subset selection is deferred to invocation time so that cross-skill
    composition works: when `_load_skills` later registers other skills into
    the same `base_registry`, they become available to skills whose
    `frontmatter.tools` whitelist names them.
    """
    handler = _make_skill_handler(
        skill=skill, provider=provider, model=model, base_registry=base_registry
    )
    parameter_schema = _build_param_schema(skill.parameters)
    return ToolEntry(
        name=skill.name,
        description=skill.description,
        parameter_schema=parameter_schema,
        handler=handler,
        is_async=False,
    )


_TYPE_MAP = {
    "string": "string",
    "str": "string",
    "int": "integer",
    "integer": "integer",
    "bool": "boolean",
    "boolean": "boolean",
    "float": "number",
    "number": "number",
}


def _yaml_type_to_json(t: str) -> str:
    return _TYPE_MAP.get(t.lower(), "string")


def _build_param_schema(parameters: list[dict[str, Any]]) -> dict[str, Any]:
    """Generate a JSON Schema (OpenAI tool params) from a skill's parameters list.

    Empty list → fallback to the legacy `{input: string}` shape.
    Otherwise: each parameter contributes a typed property; `required` is
    populated from explicit `required: true` or from the absence of `default`.
    """
    if not parameters:
        return {
            "type": "object",
            "properties": {
                "input": {
                    "type": "string",
                    "description": (
                        "User input passed to the skill as the first user message."
                        " Optional — empty string means run the skill's default flow."
                    ),
                }
            },
        }
    properties: dict[str, Any] = {}
    required: list[str] = []
    for p in parameters:
        name = str(p.get("name") or "").strip()
        if not name:
            continue
        type_str = str(p.get("type") or "string")
        prop: dict[str, Any] = {"type": _yaml_type_to_json(type_str)}
        if "description" in p:
            prop["description"] = str(p["description"])
        if "default" in p:
            prop["default"] = p["default"]
        properties[name] = prop
        is_required = p.get("required")
        if is_required is True:
            required.append(name)
        elif is_required is False:
            pass
        elif "default" not in p:
            required.append(name)
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _check_skill_recursion(skill_name: str, stack: tuple[str, ...]) -> str | None:
    """Return a `<error: ...>` string when the skill would recurse or exceed depth."""
    if skill_name in stack:
        return f"<error: skill cycle detected: {' -> '.join((*stack, skill_name))}>"
    if len(stack) >= _MAX_SKILL_DEPTH:
        chain = " -> ".join((*stack, skill_name))
        return f"<error: skill depth limit ({_MAX_SKILL_DEPTH}) exceeded: {chain}>"
    return None


def _resolve_skill_invocation(skill: Skill, kwargs: dict[str, Any]) -> tuple[str, str]:
    """Map the model's kwargs onto (system_prompt_body, user_message).

    Two modes:
    - Legacy (no `parameters` declared): `body` stays as authored, `user_msg`
      is the `input` kwarg verbatim.
    - Typed (`parameters` declared): every `{name}` placeholder in the body is
      substituted with the kwarg; surviving kwargs are JSON-serialised into
      `user_msg` so the sub-agent can still see them.
    """
    if not skill.parameters:
        user_msg = str(kwargs["input"]) if kwargs.get("input") else "Run the workflow."
        return skill.body, user_msg

    body = skill.body
    leftover: dict[str, Any] = {}
    for name, value in kwargs.items():
        placeholder = "{" + name + "}"
        if placeholder in body:
            body = body.replace(placeholder, str(value))
        else:
            leftover[name] = value
    user_msg = json.dumps(leftover, ensure_ascii=False) if leftover else "Run the workflow."
    return body, user_msg


def _make_skill_handler(
    *,
    skill: Skill,
    provider: Provider,
    model: str,
    base_registry: Registry,
) -> Callable[..., str]:
    # Lazy import to avoid a hard import cycle (agent imports memory; skills
    # belong to the same core layer but are above agent in dependency order).
    from veles.core.agent import Agent
    from veles.core.context import (
        current_skill_stack,
        push_skill_stack,
        reset_skill_stack,
    )

    def handler(**kwargs: Any) -> str:
        recursion_error = _check_skill_recursion(skill.name, current_skill_stack())
        if recursion_error is not None:
            return recursion_error

        body, user_msg = _resolve_skill_invocation(skill, kwargs)

        # Defer subset to invocation: by now `base_registry` contains every
        # other skill registered in the same _load_skills pass.
        sub_registry = base_registry.subset(skill.tools)
        token = push_skill_stack(skill.name)
        try:
            sub_agent = Agent(
                provider=provider,
                registry=sub_registry,
                model=model,
                max_iterations=skill.max_iterations,
                system_prompt=body,
            )
            try:
                result = sub_agent.run(user_msg)
            except Exception:
                bump_telemetry(skill, success=False)
                raise
            bump_telemetry(skill, success=result.stopped_reason == "completed")
            return result.text
        finally:
            reset_skill_stack(token)

    return handler
