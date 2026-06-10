"""`veles schema` — validate / edit AGENTS.md (M34)."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from veles.core.agents_md_schema import validate as validate_agents_md
from veles.core.project import Project


def cmd_schema_dispatch(args: argparse.Namespace) -> int:
    """Both subcommands need an active project; resolve it lazily."""
    from veles.cli import _resolve_active_project  # back-import (deferred)

    project = _resolve_active_project(args)
    if project is None:
        print(
            f"error: no Veles project found at {Path.cwd()} or any parent.",
            file=sys.stderr,
        )
        return 2
    if args.schema_command == "validate":
        return _validate(project)
    if args.schema_command == "edit":
        return _edit(project)
    if args.schema_command == "fix":
        return _fix(project)
    print(f"error: unknown schema subcommand {args.schema_command!r}", file=sys.stderr)
    return 2


def _validate(project: Project) -> int:
    p = project.agents_md_path
    if not p.is_file():
        print(f"error: AGENTS.md not found at {p}", file=sys.stderr)
        return 2
    text = p.read_text(encoding="utf-8", errors="replace")
    result = validate_agents_md(text)
    if result.ok:
        joined = ", ".join(result.present) or "(none)"
        print(f"AGENTS.md valid. Sections: {joined}")
        return 0
    print(
        f"AGENTS.md missing recommended sections: {', '.join(result.missing)}",
        file=sys.stderr,
    )
    print(f"present: {', '.join(result.present) or '(none)'}", file=sys.stderr)
    print("run `veles schema edit` to fix.", file=sys.stderr)
    return 1


def _fix(project: Project) -> int:
    """Interactively add missing AGENTS.md sections via LLM wizard."""
    from veles.core.agents_md_fixer import Question, fix_agents_md
    from veles.core.routing import route

    p = project.agents_md_path
    if not p.is_file():
        print(f"error: AGENTS.md not found at {p}", file=sys.stderr)
        return 2

    provider_name, model = route("compressor", project)

    def ask_question(q: Question) -> str:
        if q.choices:
            print(f"\n{q.text}")
            for i, c in enumerate(q.choices, 1):
                print(f"  {i}. {c}")
            print(f"  {len(q.choices) + 1}. Other (type your answer)")
            while True:
                try:
                    raw = input("> ").strip()
                except (EOFError, KeyboardInterrupt):
                    return ""
                if raw.isdigit():
                    idx = int(raw) - 1
                    if 0 <= idx < len(q.choices):
                        return q.choices[idx]
                if raw:
                    return raw
        else:
            try:
                return input(f"{q.text}\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                return ""

    added = fix_agents_md(
        p,
        project.name,
        provider=provider_name,
        model=model,
        ask_question=ask_question,
        on_section_start=lambda s: print(f"\n--- Generating: {s} ---"),
        on_section_done=lambda s: print(f"✓ Added: {s}"),
    )
    if added:
        print(f"\nAdded {len(added)} section(s): {', '.join(added)}")
    else:
        print("AGENTS.md already has all recommended sections.")
    return 0


def _edit(project: Project) -> int:
    """Open AGENTS.md in $EDITOR, then validate. The editor's exit code
    is informational — even if the user `:cq`'d, we still validate the
    on-disk file."""
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "vi"
    p = project.agents_md_path
    if not p.is_file():
        from veles.core.agents_md_schema import default_template

        p.write_text(default_template(project.name), encoding="utf-8")
        print(f"<created template at {p}>", file=sys.stderr)
    try:
        proc = subprocess.run([editor, str(p)], check=False)
    except FileNotFoundError:
        print(f"error: editor {editor!r} not found in PATH", file=sys.stderr)
        return 2
    if proc.returncode != 0:
        print(
            f"warning: editor exited with code {proc.returncode}",
            file=sys.stderr,
        )
    return _validate(project)
