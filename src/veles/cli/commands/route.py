"""`veles route` — inspect / edit ensemble routing (M43, unified in M125).

M125 moved per-task routes from a standalone `routing.toml` into
`config.toml [routing.tasks]` and made `[provider]` the routing base, so
`set`/`reset` now read-modify-write `config.toml` and `show` resolves
through `effective_route` (same precedence the agent uses). M149 removed
the legacy auto-import and the `migrate` verb — `config.toml` is the
single source of truth.
"""

from __future__ import annotations

import argparse
import sys

from veles.core.project import Project
from veles.core.routing import (
    DEFAULT_TASKS,
    effective_route,
    load_nl_routing_config,
    load_routing_config,
    parse_spec,
    reset_project_route,
    set_project_route,
)


def cmd_route(args: argparse.Namespace, project: Project) -> int:
    sub = args.route_command
    if sub == "show":
        return _show(project)
    if sub == "set":
        return _set(args, project)
    if sub == "reset":
        return _reset(args, project)
    if sub == "refresh":
        return _refresh(args, project)
    print(f"error: unknown route subcommand {sub!r}", file=sys.stderr)
    return 2


def _show(project: Project) -> int:
    from veles.core.project_config import get_section, load_project_config
    from veles.core.user_config import get_user_section

    manual = load_routing_config(project)
    nl_config = load_nl_routing_config(project)
    user_routes = get_user_section("routing", "tasks")
    task_names = sorted(
        {
            *DEFAULT_TASKS.keys(),
            *manual.tasks.keys(),
            *nl_config.tasks.keys(),
            *user_routes.keys(),
        }
    )
    print(f"{'task':<14}  {'spec':<40}  source")
    for task in task_names:
        provider, model, source = effective_route(task, project)
        print(f"{task:<14}  {f'{provider}:{model}':<40}  {source}")

    # Surface an incomplete `[provider]` base — a common footgun where
    # `default` is set but `model` is not, so the base layer is skipped.
    prov = get_section(load_project_config(project), "provider")
    if prov.get("default") and not prov.get("model"):
        print(
            f"\nnote: [provider] default={prov['default']!r} has no model — "
            "the project-provider base layer is skipped (set [provider].model "
            "or an explicit route).",
            file=sys.stderr,
        )
    return 0


def _set(args: argparse.Namespace, project: Project) -> int:
    try:
        parse_spec(args.spec)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    set_project_route(project, args.task, args.spec)
    print(f"<routed {args.task!r} → {args.spec}>", file=sys.stderr)
    return 0


def _refresh(args: argparse.Namespace, project: Project) -> int:
    """M43b — re-parse natural-language routing hints from AGENTS.md.

    `--force` re-runs even when the AGENTS.md SHA matches the stored
    state. Without it, an unchanged AGENTS.md short-circuits to the
    existing nl-state (rc=0 + a friendly "unchanged" message).
    """
    from veles.cli import _has_api_key_for_provider, _make_provider
    from veles.core.project import load_agents_md
    from veles.core.routing import make_nl_extractor, refresh_nl_routing, route

    agents_md = load_agents_md(project) or ""
    if not agents_md.strip():
        print(
            "AGENTS.md is missing or empty — nothing to parse.",
            file=sys.stderr,
        )
        return 1

    # Route the extractor itself via the `default` task so the user can
    # cheap-it-out by setting the default to a haiku-tier model via
    # `veles route set default <provider>:<haiku-model>`.
    routed_provider, routed_model = route("default", project)
    if not _has_api_key_for_provider(routed_provider):
        print(
            f"error: no API key for routed provider {routed_provider!r}; "
            "set the env var or `veles route set default <provider>:<model>`",
            file=sys.stderr,
        )
        return 2
    try:
        provider_obj = _make_provider(routed_provider)
    except Exception as exc:
        print(f"error: failed to build provider {routed_provider!r}: {exc}", file=sys.stderr)
        return 2

    extractor = make_nl_extractor(provider=provider_obj, model=routed_model)
    state = refresh_nl_routing(
        project, agents_md, extractor=extractor, force=bool(args.force)
    )
    if state.entries_count:
        print(
            f"<refreshed nl routing: {state.entries_count} entries from AGENTS.md>",
            file=sys.stderr,
        )
    else:
        print(
            "<refreshed nl routing: no actionable hints found in AGENTS.md>",
            file=sys.stderr,
        )
    return 0


def _reset(args: argparse.Namespace, project: Project) -> int:
    changed = reset_project_route(project, args.task)
    if args.task is None:
        print(
            "<reset all routing entries to default>"
            if changed
            else "<no project routes set; nothing to reset>",
            file=sys.stderr,
        )
        return 0
    print(
        f"<reset {args.task!r} to default>"
        if changed
        else f"<{args.task!r} already at default; nothing to reset>",
        file=sys.stderr,
    )
    return 0
