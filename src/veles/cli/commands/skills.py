"""`veles skill` — list / show / add / remove / promote / demote (M5/M19/M23/M40)."""

from __future__ import annotations

import argparse
import sys

from veles.core.critical_ops import confirm_critical
from veles.core.project import Project
from veles.core.skill_install import (
    SkillInstallError,
    SkillNotFoundError,
    _derive_name,
    demote_skill,
    install_skill_from_source,
    promote_skill,
    remove_skill,
)
from veles.core.skills import discover_skills, user_skills_dir


def cmd_skill(args: argparse.Namespace, project: Project) -> int:
    if args.skill_command == "list":
        return _list(project)
    if args.skill_command == "show":
        return _show(project, args.name)
    if args.skill_command == "add":
        return _add(args, project)
    if args.skill_command == "remove":
        return _remove(args, project)
    if args.skill_command == "dedup":
        return _dedup(args, project)
    if args.skill_command == "suggest-promote":
        return _suggest_promote(args, project)
    if args.skill_command == "promote":
        return _promote(args, project)
    if args.skill_command == "demote":
        return _demote(args, project)
    return 2


def _dedup(args: argparse.Namespace, project: Project) -> int:
    """M61 — find near-duplicate skills via embedding or TF-IDF similarity."""
    from veles.core.model_resolver import ConfigurationError
    from veles.core.skill_dedup import find_duplicate_skills

    skills = discover_skills(project)
    if len(skills) < 2:
        print("(need at least 2 skills to look for duplicates)")
        return 0
    threshold_embedding = args.embedding_threshold
    threshold_tfidf = args.tfidf_threshold
    try:
        clusters, mode = find_duplicate_skills(
            skills,
            project=project,
            mode=args.mode,
            embedding_threshold=threshold_embedding,
            tfidf_threshold=threshold_tfidf,
        )
    except (ConfigurationError, RuntimeError) as exc:
        # `--mode embedding` (explicit) needs a configured embedding model;
        # `--mode auto` would have degraded to tfidf. Clean error, not a
        # traceback. (M165d: there is no hardcoded embedding default.)
        print(
            f"error: embedding similarity is unavailable: {exc}\n"
            "Set `[routing.tasks].embedding` (e.g. openai:text-embedding-3-small) "
            "in <project>/.veles/config.toml, or use `--mode tfidf`.",
            file=sys.stderr,
        )
        return 2
    if not clusters:
        print(f"no duplicate clusters found (mode={mode}).")
        return 0
    print(f"found {len(clusters)} duplicate cluster(s) using {mode} similarity:\n")
    for cluster in clusters:
        names = ", ".join(s.name for s in cluster.skills)
        print(f"[score={cluster.score:.2f}]  {names}")
        for s in cluster.skills:
            print(f"  - {s.name}  (scope={s.scope}, use={s.use_count})  {s.description[:60]}")
        print()
    return 0


def _suggest_promote(args: argparse.Namespace, project: Project) -> int:
    """M61 — list project-scope skills that meet the auto-promote bar."""
    from veles.core.skill_promotion import find_promote_candidates, write_promote_proposals

    candidates = find_promote_candidates(
        project,
        min_uses=args.min_uses,
        min_success_rate=args.min_success_rate,
    )
    if not candidates:
        print("(no project-scope skills meet the auto-promote threshold yet)")
        return 0
    print(f"found {len(candidates)} promotion candidate(s):\n")
    for c in candidates:
        print(
            f"  {c.skill.name:<22}  use={c.skill.use_count:>4}  "
            f"success={int(c.success_rate * 100):>3}%  {c.skill.description[:60]}"
        )
    if args.save:
        written = write_promote_proposals(project, candidates)
        print(f"\nwrote {len(written)} proposal page(s) under .veles/memory/proposals/.")
    else:
        print("\n(pass --save to persist these as .veles/memory/proposals/promote-<name>.md pages)")
    return 0


def _list(project: Project) -> int:
    skills = discover_skills(project)
    if not skills:
        print("(no skills)")
        return 0
    header = (
        f"{'name':<22}  {'scope':<7}  {'use':>5}  {'success':>7}  {'error':>5}  "
        f"{'last_used':<22}  description"
    )
    print(header)
    for s in skills:
        last = s.last_used or "—"
        desc = s.description if len(s.description) <= 50 else s.description[:47] + "..."
        print(
            f"{s.name:<22}  {s.scope:<7}  {s.use_count:>5}  {s.success_count:>7}  "
            f"{s.error_count:>5}  {last:<22}  {desc}"
        )
    return 0


def _show(project: Project, name: str) -> int:
    skills = discover_skills(project)
    for s in skills:
        if s.name == name:
            print(s.path.read_text(encoding="utf-8"))
            return 0
    print(f"error: skill {name!r} not found in {project.skills_dir}", file=sys.stderr)
    return 1


def _add(args: argparse.Namespace, project: Project) -> int:
    scope = args.scope
    target_dir = user_skills_dir() if scope == "user" else project.skills_dir
    target_name = args.name or _derive_name(args.source)
    target = target_dir / target_name
    summary = (
        f"Source: {args.source}\n"
        f"Target: {target} ({scope}-scope)\n"
        "Installing a skill places third-party code that the agent can invoke. "
        "Review the source before confirming."
    )
    if not confirm_critical(f"install skill from {args.source} ({scope}-scope)", summary):
        print("<aborted>", file=sys.stderr)
        return 1
    try:
        skill = install_skill_from_source(
            args.source, project=project, name_override=args.name, scope=scope
        )
    except SkillInstallError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(
        f"<installed skill {skill.name!r} ({scope}-scope) at {skill.path.parent}>",
        file=sys.stderr,
    )
    return 0


def _remove(args: argparse.Namespace, project: Project) -> int:
    from veles.cli import _confirm  # back-import (deferred)

    scope = args.scope
    target_dir = user_skills_dir() if scope == "user" else project.skills_dir
    target = target_dir / args.name
    if not args.yes and not _confirm(
        f"Remove skill {args.name!r} ({scope}-scope, {target})? [y/N]"
    ):
        print("<aborted>", file=sys.stderr)
        return 1
    try:
        remove_skill(args.name, project=project, scope=scope)
    except SkillNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"<removed skill {args.name!r} ({scope}-scope)>", file=sys.stderr)
    return 0


def _promote(args: argparse.Namespace, project: Project) -> int:
    summary = (
        f"Skill: {args.name}\n"
        f"Source: {project.skills_dir / args.name}\n"
        f"Target: {user_skills_dir() / args.name} (user-global)\n"
        "This installs executable code into user-global storage shared "
        "across all projects. Telemetry counters will be "
        f"{'preserved' if args.keep_telemetry else 'reset'}."
    )
    if not confirm_critical(f"promote skill {args.name!r} to user scope", summary):
        print("<aborted>", file=sys.stderr)
        return 1
    try:
        dst = promote_skill(args.name, project=project, reset_telemetry=not args.keep_telemetry)
    except (SkillNotFoundError, SkillInstallError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"<promoted skill {args.name!r} to {dst}>", file=sys.stderr)
    return 0


def _demote(args: argparse.Namespace, project: Project) -> int:
    from veles.cli import _confirm  # back-import (deferred)

    target = project.skills_dir / args.name
    if not args.yes and not _confirm(
        f"Demote skill {args.name!r} from user-global to {target}? [y/N]"
    ):
        print("<aborted>", file=sys.stderr)
        return 1
    try:
        dst = demote_skill(args.name, project=project)
    except (SkillNotFoundError, SkillInstallError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"<demoted skill {args.name!r} to {dst}>", file=sys.stderr)
    return 0
