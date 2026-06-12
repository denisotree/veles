"""Parser for `veles skill {list,show,add,remove,promote,demote,dedup,suggest-promote}`."""

from __future__ import annotations

import argparse

from veles.cli._parsers._common import add_project_root_flag


def register(sub: argparse._SubParsersAction) -> None:
    skill = sub.add_parser("skill", help="Manage project skills.")
    add_project_root_flag(skill)
    skill_sub = skill.add_subparsers(dest="skill_command", required=True)

    skill_sub.add_parser("list", help="List skills in the active project.")

    skill_show = skill_sub.add_parser("show", help="Print a skill's SKILL.md verbatim.")
    skill_show.add_argument("name", help="Skill name.")

    skill_add = skill_sub.add_parser(
        "add", help="Install a skill from a git URL or local directory."
    )
    skill_add.add_argument("source", help="Git URL (https://, ssh://, git@, *.git) or local path.")
    skill_add.add_argument(
        "--name",
        default=None,
        help="Override the install name (default: derived from source).",
    )
    skill_add.add_argument(
        "--scope",
        choices=["project", "user"],
        default="project",
        help="Install at project (default) or user-global (~/.veles/skills) scope.",
    )
    skill_add.add_argument("--yes", "-y", action="store_true", help="Skip the confirmation prompt.")

    skill_remove = skill_sub.add_parser("remove", help="Delete an installed skill.")
    skill_remove.add_argument("name", help="Skill name to remove.")
    skill_remove.add_argument(
        "--scope",
        choices=["project", "user"],
        default="project",
        help="Remove from project (default) or user-global scope.",
    )
    skill_remove.add_argument(
        "--yes", "-y", action="store_true", help="Skip the confirmation prompt."
    )

    skill_promote = skill_sub.add_parser(
        "promote",
        help="Copy a project-scope skill to user-global scope (~/.veles/skills).",
    )
    skill_promote.add_argument("name", help="Skill name to promote.")
    skill_promote.add_argument(
        "--keep-telemetry",
        action="store_true",
        help="Preserve use/success/error counters (default: reset on promote).",
    )

    skill_demote = skill_sub.add_parser(
        "demote", help="Copy a user-global skill to the active project's scope."
    )
    skill_demote.add_argument("name", help="Skill name to demote.")
    skill_demote.add_argument(
        "--yes", "-y", action="store_true", help="Skip the confirmation prompt."
    )

    skill_dedup = skill_sub.add_parser(
        "dedup",
        help=(
            "Find near-duplicate skills via embedding or TF-IDF cosine "
            "similarity. Cache lives at `<project>/.veles/skill_embeddings.json`."
        ),
    )
    skill_dedup.add_argument(
        "--mode",
        choices=("auto", "tfidf", "embedding"),
        default="auto",
        help=(
            "Similarity backend (default: auto = try embedding, fall back to "
            "tfidf when no API key for the routed embedding provider)."
        ),
    )
    skill_dedup.add_argument(
        "--embedding-threshold",
        type=float,
        default=0.85,
        metavar="F",
        help="Cosine similarity threshold for the embedding path (default: 0.85).",
    )
    skill_dedup.add_argument(
        "--tfidf-threshold",
        type=float,
        default=0.50,
        metavar="F",
        help="Cosine similarity threshold for the TF-IDF path (default: 0.50).",
    )

    skill_suggest_promote = skill_sub.add_parser(
        "suggest-promote",
        help=(
            "List project-scope skills that meet the auto-promote bar "
            "(use_count + success_rate). --save persists proposals into "
            ".veles/memory/proposals/."
        ),
    )
    skill_suggest_promote.add_argument(
        "--save",
        action="store_true",
        help="Persist each candidate as .veles/memory/proposals/promote-<name>.md.",
    )
    skill_suggest_promote.add_argument(
        "--min-uses",
        type=int,
        default=10,
        metavar="N",
        help="Minimum invocation count to qualify (default: 10).",
    )
    skill_suggest_promote.add_argument(
        "--min-success-rate",
        type=float,
        default=0.7,
        metavar="F",
        help="Minimum success_rate to qualify (0..1, default: 0.7).",
    )
