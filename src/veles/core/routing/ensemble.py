"""Ensemble routing (M43, unified in M125) — `(provider, model)` per task.

VISION §5.3.1: Veles isn't pinned to a single backend. Different tasks
benefit from different model classes — planning wants the strongest
available, scaffolding wants the cheapest, summarisation wants a fast
mid-tier. The typed config layer lives in the project's `config.toml`:

    <project>/.veles/config.toml

    [routing.tasks]
    default     = "openrouter:anthropic/claude-sonnet-4.6"
    compressor  = "ollama:qwen3:4b-instruct"

Each entry is a `<provider>:<model>` string. `<provider>` matches
Veles' CLI provider names (`openrouter`, `anthropic`, `openai`,
`gemini`, `claude-cli`, `gemini-cli`); `<model>` is whatever the chosen
provider expects (slug for OpenRouter, bare name for direct adapters).

**M125 — config unification + `[engine]` as routing base.** Before
M125 these task routes lived in a separate `<project>/.veles/routing.toml`
that had *zero* interaction with `config.toml [engine]` (which only
ever fed the main agent). A user who set `[engine] provider = "ollama"`
for a fully-local project still had compressor/insights silently hit the
hard-coded `openrouter:anthropic/claude-haiku-4.5` default → 404. M125
folds `[routing.tasks]` into `config.toml`, makes `[engine]` the base
layer for every ensemble task, and mirrors M124-perm-unify's project →
user → hardcoded layering (see `core/permission/policy.py::effective_policy`
and `core/model_resolver.py`). M149 removed the pre-M125 standalone
`routing.toml` auto-import — `config.toml` is the single source of truth.

Resolution order in `effective_route(task_type, project)` — first hit wins:
1.  project `[routing.tasks][task_type]`        (label `project-route`)
2.  project `[routing.tasks].default`           (`project-route-default`)
3.  project NL `routing.nl.toml`  [task_type]   (`nl`)
4.  project NL `routing.nl.toml`  default        (`nl-default`)
5.  project `[engine]` base  (M125)              (`project-provider`)
6.  user `[routing.tasks][task_type]`  (M125)    (`user-route`)
7.  user `[routing.tasks].default`  (M125)       (`user-route-default`)
8.  user `[user] default_provider/model`  (M125) (`user-provider`)

M165c: there is **no hardcoded cloud catch-all** below layer 8 for chat
tasks — consistent with M165's empty `DEFAULT_MODEL`. When none of layers
1–8 resolve, `effective_route` raises `ConfigurationError` (the same error
type System A raises) instead of silently using `openrouter:claude-*`.
Sub-agent callers (compressor, advisor, insights, vision, …) catch it and
degrade — the feature goes off, never silently cloud.

NL sits *above* the `[engine]` base on purpose: a complete `[engine]`
yields a spec for every task, so placed above NL it would shadow every
per-task AGENTS.md hint. `embedding` bypasses the base (see `effective_route`):
a chat base model is not an embedding model, so only an explicit
`[routing.tasks].embedding` answers it — with none set it raises like any other
task (M165d), and its sole consumer (skill_dedup) degrades to tfidf in auto mode.

Missing or malformed *config* degrades to the next layer silently — routing
should never block on a typo; only a fully-unconfigured chat task raises.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from veles.core.project import Project

# M165c/M165d: no hardcoded cloud fallback anywhere. Every task — chat tasks
# (default/curator/compressor/insights/skills/advisor/vision) and `embedding` —
# resolves from `[routing.tasks]`, the `[engine]` base (chat tasks only; see
# the embedding bypass in `effective_route`), or `default_provider/model`. When
# nothing is configured `effective_route` raises `ConfigurationError` instead of
# silently using a cloud model; callers catch it and degrade (skip the feature).

# The canonical set of routable task names — used by NL-route validation,
# `veles route show`, and the self-doc routing block to answer "is this a known
# task?" (independent of whether the task is actually configured).
KNOWN_TASKS: frozenset[str] = frozenset(
    {"default", "curator", "compressor", "insights", "skills", "advisor", "vision", "embedding"}
)


@dataclass(slots=True)
class RoutingConfig:
    tasks: dict[str, str] = field(default_factory=dict)


def _filter_specs(raw: dict[str, Any]) -> dict[str, str]:
    """Keep only `str → <provider>:<model>` entries (drop non-string keys/
    values and bare specs without a `:`)."""
    out: dict[str, str] = {}
    for name, spec in raw.items():
        if isinstance(name, str) and isinstance(spec, str) and ":" in spec:
            out[name] = spec
    return out


def load_routing_config(project: Project) -> RoutingConfig:
    """Read project task routes from `config.toml [routing.tasks]` (M125).

    Silent on purpose — `route()` calls this every agent turn. Returns an
    empty config (→ defaults) when nothing is set."""
    from veles.core.project_config import get_section, load_project_config

    config_tasks = _filter_specs(get_section(load_project_config(project), "routing", "tasks"))
    return RoutingConfig(tasks=config_tasks)


def set_project_route(project: Project, task: str, spec: str) -> None:
    """Write one per-task route into `config.toml [routing.tasks]` (M125).

    Read-modify-write through the canonical `project_config` saver so the
    rest of the file (provider / daemon / channels) is preserved."""
    from veles.core.project_config import load_project_config, save_project_config

    cfg = load_project_config(project)
    cfg.setdefault("routing", {}).setdefault("tasks", {})[task] = spec
    save_project_config(project, cfg)


def reset_project_route(project: Project, task: str | None = None) -> bool:
    """Remove one task route (or all, when `task is None`) from
    `config.toml [routing.tasks]`. Returns True when something changed."""
    from veles.core.project_config import load_project_config, save_project_config

    cfg = load_project_config(project)
    routing = cfg.get("routing")
    if not isinstance(routing, dict):
        return False
    tasks = routing.get("tasks")
    if not isinstance(tasks, dict):
        return False
    if task is None:
        if not tasks:
            return False
        routing["tasks"] = {}
        save_project_config(project, cfg)
        return True
    if task not in tasks:
        return False
    del tasks[task]
    save_project_config(project, cfg)
    return True


def provider_to_spec(provider: str | None, model: str | None) -> str | None:
    """Turn a `[engine]`/`[user]` base into a routing spec, or `None`.

    A base contributes a layer ONLY when BOTH provider and model are set.
    We never synthesize `<provider>:DEFAULT_MODEL` — `DEFAULT_MODEL`
    (`anthropic/claude-sonnet-4.6`) is an OpenRouter slug; pairing it with
    e.g. `ollama` re-creates the exact 404 M125 exists to kill."""
    if provider and model:
        return f"{provider}:{model}"
    return None


def _first_spec(
    candidates: list[tuple[str | None, str]],
    task_type: str,
) -> tuple[str, str, str]:
    """Return `(provider, model, source_label)` for the first candidate
    whose spec is non-empty and parses cleanly. Malformed specs (e.g. a
    user typo like `anthropic:`) are skipped rather than crashing a turn.

    M165c: when no candidate resolves there is no hardcoded cloud fallback —
    raise `ConfigurationError` (lazy import to keep `ensemble` free of the
    cli/config stack). Sub-agent callers catch it and degrade."""
    for spec, label in candidates:
        if not spec:
            continue
        try:
            provider, model = parse_spec(spec)
        except ValueError:
            continue
        return (provider, model, label)
    from veles.core.model_resolver import ConfigurationError

    raise ConfigurationError(
        f"no model configured for routed task {task_type!r}. Set `[engine]` "
        "(provider + model) or `default_provider`/`default_model` in "
        f"~/.veles/config.toml, or `[routing.tasks].{task_type}` in "
        "<project>/.veles/config.toml."
    )


def effective_route(task_type: str, project: Project) -> tuple[str, str, str]:
    """Return `(provider, model, source_label)` for `task_type` (M125).

    The layered resolution (project → user → hardcoded) mirrors M124's
    `effective_policy`; `route()` is the thin `(provider, model)` wrapper.
    Both this and `veles route show` consume it so the precedence has a
    single source of truth. See the module docstring for the full order."""
    # Lazy imports — keep `ensemble` importable from low-level modules
    # without dragging the config/user-config stack in at import time.
    from veles.core.user_config import get_user_section

    proj_routes = load_routing_config(project).tasks
    user_routes = get_user_section("routing", "tasks")

    # EMBEDDING BYPASS — a chat base model (e.g. ollama:qwen3) is not an
    # embedding model, so `embedding` must never inherit a `[engine]`/`[user]`
    # base or any `default` catch-all. Only an explicit per-task route answers
    # it; with none configured `_first_spec` raises (M165d removed the hardcoded
    # `openai:text-embedding-3-small` default — its one consumer, skill_dedup,
    # degrades to tfidf in auto mode and errors clearly under `--mode embedding`).
    if task_type == "embedding":
        return _first_spec(
            [
                (proj_routes.get("embedding"), "project-route"),
                (user_routes.get("embedding"), "user-route"),
            ],
            task_type,
        )

    # Lazy import — `nl_override` imports back from `ensemble`, would
    # deadlock if hoisted to the module top.
    from veles.core.routing.nl_override import load_nl_routing_config

    nl = load_nl_routing_config(project).tasks

    from veles.core.project_config import get_section, load_project_config
    from veles.core.user_config import load_user_config

    proj_prov = get_section(load_project_config(project), "engine")
    proj_base = provider_to_spec(proj_prov.get("provider"), proj_prov.get("model"))

    user_cfg = load_user_config()
    user_base = (
        provider_to_spec(user_cfg.default_provider, user_cfg.default_model)
        if user_cfg is not None
        else None
    )

    return _first_spec(
        [
            (proj_routes.get(task_type), "project-route"),
            (proj_routes.get("default"), "project-route-default"),
            (nl.get(task_type), "nl"),
            (nl.get("default"), "nl-default"),
            (proj_base, "project-provider"),
            (user_routes.get(task_type), "user-route"),
            (user_routes.get("default"), "user-route-default"),
            (user_base, "user-provider"),
            # No hardcoded cloud catch-all (M165c): if none of the above
            # resolved, `_first_spec` raises ConfigurationError.
        ],
        task_type,
    )


def route(task_type: str, project: Project) -> tuple[str, str]:
    """Return `(provider_name, model)` for `task_type`. Thin wrapper over
    `effective_route` (drops the source label)."""
    provider, model, _ = effective_route(task_type, project)
    return (provider, model)


def parse_spec(spec: str) -> tuple[str, str]:
    """Split `<provider>:<model>` into a tuple.

    Specs without a `:` are treated as bare OpenRouter model slugs (e.g.
    `"anthropic/claude-sonnet-4.6"` → `("openrouter", "anthropic/claude-sonnet-4.6")`).
    Empty inputs raise `ValueError`.
    """
    if not spec:
        raise ValueError("routing spec must not be empty")
    if ":" not in spec:
        return ("openrouter", spec)
    provider, _, model = spec.partition(":")
    provider = provider.strip()
    model = model.strip()
    if not provider:
        provider = "openrouter"
    if not model:
        raise ValueError(f"routing spec {spec!r} has empty model")
    return (provider, model)
