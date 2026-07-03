"""Live "what exists in Veles" skeleton, derived from code so it never rots.

Sources: the argparse command/flag tree (`cli._parsers.build_parser`), builtin
skills (`mount_builtin_skills`), and builtin tools (the `@tool` registry). The
skeleton backs both the knowledge search (fresh facts) and the freshness guard
(`related` refs in curated notes are validated against `skeleton_ref_index`).
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SkeletonEntry:
    kind: str  # "cmd" | "flag" | "skill" | "tool"
    name: str
    summary: str
    aliases: list[str] = field(default_factory=list)


def _walk_commands(entries: list[SkeletonEntry]) -> None:
    from veles.cli._parsers import build_parser

    parser = build_parser()
    for action in parser._actions:
        if not isinstance(action, argparse._SubParsersAction):
            continue
        for cmd_name, subparser in action.choices.items():
            help_text = (subparser.description or "").strip()
            sub_names: list[str] = []
            entries.append(SkeletonEntry(kind="cmd", name=cmd_name, summary=help_text))
            for sub_action in subparser._actions:
                # Flags on this command.
                for opt in sub_action.option_strings:
                    if opt.startswith("--"):
                        entries.append(
                            SkeletonEntry(
                                kind="flag",
                                name=f"{cmd_name}:{opt}",
                                summary=(sub_action.help or "").strip(),
                            )
                        )
                # Nested subcommands (e.g. `skill list`) recorded as aliases.
                if isinstance(sub_action, argparse._SubParsersAction):
                    sub_names.extend(sub_action.choices.keys())
            if sub_names:
                entries.append(
                    SkeletonEntry(
                        kind="cmd",
                        name=cmd_name,
                        summary=help_text,
                        aliases=sorted(set(sub_names)),
                    )
                )


def _walk_skills(entries: list[SkeletonEntry]) -> None:
    from veles.core.skills import mount_builtin_skills

    for skill in mount_builtin_skills():
        entries.append(
            SkeletonEntry(kind="skill", name=skill.name, summary=skill.description or "")
        )


def _walk_tools(entries: list[SkeletonEntry]) -> None:
    import veles.core.tools.builtin  # noqa: F401  (fires @tool registration)
    from veles.core.tools.registry import registry

    for name in registry.list_names():
        try:
            desc = registry.get(name).description or ""
        except KeyError:
            desc = ""
        entries.append(SkeletonEntry(kind="tool", name=name, summary=desc))


def build_skeleton() -> list[SkeletonEntry]:
    entries: list[SkeletonEntry] = []
    _walk_commands(entries)
    _walk_skills(entries)
    _walk_tools(entries)
    return entries


def skeleton_ref_index(entries: list[SkeletonEntry]) -> set[str]:
    """Valid `related`-ref strings for the freshness guard."""
    return {f"{e.kind}:{e.name}" for e in entries}
