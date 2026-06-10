"""`veles subproject` — vertical-subproject registry management (M41)."""

from __future__ import annotations

import argparse
import sys

from veles.core.project import Project, ProjectAlreadyExists
from veles.core.subproject import (
    init_subproject,
    load_subprojects,
    resolve_subproject_path,
    unregister_subproject,
)
from veles.core.subproject_proposer import (
    Cluster,
    detect_clusters,
    write_proposals,
)


def cmd_subproject(args: argparse.Namespace, project: Project) -> int:
    sub = args.subproject_command
    if sub == "init":
        return _init(args, project)
    if sub == "list":
        return _list(project)
    if sub == "switch":
        return _switch(args, project)
    if sub == "remove":
        return _remove(args, project)
    if sub == "suggest":
        return _suggest(args, project)
    print(f"error: unknown subproject subcommand {sub!r}", file=sys.stderr)
    return 2


def _init(args: argparse.Namespace, project: Project) -> int:
    try:
        sub_project = init_subproject(
            project,
            args.subdir,
            name=args.name,
            description=args.description,
        )
    except (ValueError, ProjectAlreadyExists) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(
        f"<initialised subproject {sub_project.name!r} at {sub_project.root}>",
        file=sys.stderr,
    )
    return 0


def _list(project: Project) -> int:
    subs = load_subprojects(project)
    if not subs:
        print("(no subprojects registered)")
        return 0
    for s in subs:
        abs_path = resolve_subproject_path(project, s)
        marker = "" if abs_path.is_dir() else "  (missing)"
        print(f"{s.slug:<22}  {s.path:<24}  {s.description}{marker}")
    return 0


def _switch(args: argparse.Namespace, project: Project) -> int:
    for s in load_subprojects(project):
        if s.slug == args.slug:
            print(resolve_subproject_path(project, s))
            return 0
    print(
        f"error: no subproject named {args.slug!r} registered under {project.root}",
        file=sys.stderr,
    )
    return 2


def _remove(args: argparse.Namespace, project: Project) -> int:
    if not unregister_subproject(project, args.slug):
        print(
            f"error: no subproject named {args.slug!r} in {project.root}",
            file=sys.stderr,
        )
        return 1
    print(f"<unregistered subproject {args.slug!r}>", file=sys.stderr)
    return 0


def _suggest(args: argparse.Namespace, project: Project) -> int:
    clusters = detect_clusters(
        project,
        min_pages=args.min_pages,
        min_similarity=args.min_similarity,
    )
    if not clusters:
        print("no thematic clusters found in wiki/concepts + wiki/entities.")
        return 0

    _print_clusters(clusters)
    if args.save:
        written = write_proposals(project, clusters)
        print(f"\nwrote {len(written)} proposal page(s) under wiki/proposals/.")
    else:
        print("\n(pass --save to persist these as wiki/proposals/<slug>.md pages)")
    return 0


def _print_clusters(clusters: list[Cluster]) -> None:
    for cluster in clusters:
        print(f"\n[{cluster.slug}]  score={cluster.score:.2f}  pages={len(cluster.pages)}")
        print(f"  {cluster.rationale}")
        for rel in cluster.pages:
            print(f"  - {rel}")
