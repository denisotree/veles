"""`veles organize` — layout-driven project tidy-up (M175).

Propose-then-apply: the default run uses a read-only toolset and the agent's
final answer (a reorganization plan) is persisted to
`.veles/memory/proposals/organize-<ts>.md`; `--apply` re-runs with the
mutation toolset (`move_file`, `edit_file`, and — on wiki layouts —
`wiki_rename_page` etc.) so the plan is executed. The recipe itself comes
from the active layout pack's `organize` skill (see `dispatcher`), so the
behaviour is layout-specific by construction.
"""

from __future__ import annotations

import argparse
import sys
import time

from veles.core.layout.engines import wiki_enabled
from veles.core.memory.artefacts import proposals_dir, write_proposal
from veles.core.project import Project
from veles.core.tools.toolsets import TOOLSETS
from veles.modules.organize.dispatcher import resolve_operation

_OP_NAME = "organize"


def _latest_dream_findings(project: Project, *, max_chars: int = 2_000) -> str:
    """Return a truncated excerpt of the most recent dream-lint proposal, if any.

    Organize consumes dream's orphan/duplicate/stale findings as context so
    its plan can act on them. Absent any dream run, returns "".
    """
    pdir = proposals_dir(project)
    if not pdir.is_dir():
        return ""
    dreams = sorted(pdir.glob("dream-*.md"))
    if not dreams:
        return ""
    text = dreams[-1].read_text(encoding="utf-8")
    return text[:max_chars]


def _user_message(project: Project, *, scope: str | None, apply: bool) -> str:
    mode = (
        "APPLY mode: execute the reorganization now using your mutation tools "
        "(move/rename files, repair links, dedup). Make the smallest set of "
        "changes that achieves a clean layout, and log what you did."
        if apply
        else "PROPOSE mode: do NOT modify any files. Produce a concrete "
        "reorganization PLAN — list each move/rename/link/edit you would make "
        "and why. Your final message IS the plan; it will be saved for review."
    )
    parts = [mode]
    if scope:
        parts.append(f"\nScope: restrict your attention to `{scope}`.")
    findings = _latest_dream_findings(project)
    if findings:
        parts.append("\nRecent dream-lint findings to consider:\n" + findings)
    return "\n".join(parts)


def run_organize(args: argparse.Namespace, project: Project) -> int:
    """Entry point for `veles organize`. Returns a process exit code."""
    from veles.cli import (
        _PROVIDER_API_KEY_ENVS,
        _ensure_api_key,
        _print_run_summary,
        _run_agent_streaming_aware,
        _warn_if_agents_md_invalid,
        build_command_agent,
    )

    resolved = resolve_operation(project, _OP_NAME)
    if resolved is None:
        print(
            f"error: the active layout pack {project.layout_name!r} exposes no "
            "`organize` operation — nothing to reorganize.\n"
            'Switch to a layout that declares one (e.g. "llm-wiki" or '
            '"notes" in .veles/project.toml), or add an `[[layout.operations]] '
            'name = "organize"` entry to your custom pack.',
            file=sys.stderr,
        )
        return 2

    if args.provider in _PROVIDER_API_KEY_ENVS and not _ensure_api_key(args.provider):
        return 2

    apply = bool(getattr(args, "apply", False))
    scope = getattr(args, "scope", None)

    # Register the module's reorg primitive (`move_file`) so the apply
    # toolset can resolve it — lazy, exactly like the wiki engine.
    import veles.modules.organize.tools  # noqa: F401

    _warn_if_agents_md_invalid(project)
    if wiki_enabled(project):
        from veles.modules.wiki.wiki import Wiki

        Wiki(project.wiki_root).ensure_layout()

    toolset = "organize" if apply else "builtin"
    tools = TOOLSETS[toolset]
    system_prompt = (
        resolved.body
        + "\n\nYou are running as the `organize` operation. "
        + (
            "You MAY move, rename, edit, and relink files."
            if apply
            else "You are in PROPOSE mode and MUST NOT modify any files — only plan."
        )
    )

    agent = build_command_agent(
        args,
        project,
        tools=tools,
        system_prompt=system_prompt,
        check_api_key=False,
        tool_aware=True,
    )
    if agent is None:
        return 2

    result, budget = _run_agent_streaming_aware(
        agent, _user_message(project, scope=scope, apply=apply), args, project=project
    )
    _print_run_summary(args, result, budget)

    if not apply:
        slug = f"organize-{int(time.time())}"
        path = write_proposal(
            project,
            slug=slug,
            title="Organize plan",
            content=result.text or "(the agent produced no plan)",
        )
        print(f"\nproposal written: {path}\nreview it, then run `veles organize --apply`.")

    return 0 if result.stopped_reason == "completed" else 1
