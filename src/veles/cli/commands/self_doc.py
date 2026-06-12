"""`veles self-doc` — generate and display project self-documentation."""

from __future__ import annotations

import argparse
import sys

from veles.core.project import Project


def cmd_self_doc(args: argparse.Namespace, project: Project | None) -> int:
    if project is None:
        print("error: no Veles project found", file=sys.stderr)
        return 2
    sub = getattr(args, "self_doc_cmd", None) or "refresh"
    if sub == "refresh":
        return _refresh(project)
    if sub == "show":
        return _show(project)
    print(f"error: unknown self-doc subcommand: {sub}", file=sys.stderr)
    return 2


def _refresh(project: Project) -> int:
    # Import builtin modules so @tool decorators fire and register entries.
    import veles.core.tools.builtin  # noqa: F401
    from veles.cli._runtime import _RUN_TOOLS
    from veles.core.self_doc import refresh_self_doc
    from veles.core.tools.registry import registry as _tool_registry

    tools: list[tuple[str, str]] = []
    for name in _RUN_TOOLS:
        try:
            entry = _tool_registry.get(name)
            tools.append((name, entry.description or ""))
        except Exception:
            tools.append((name, ""))

    rel = refresh_self_doc(project, tools=tools)
    print(f"self-doc written to {rel}")
    return 0


def _show(project: Project) -> int:
    from veles.core.wiki import Wiki

    wiki = Wiki(project.wiki_root)
    try:
        content = wiki.read_page("wiki/self-doc/overview.md")
        print(content)
    except Exception:
        print("(no self-doc yet; run `veles self-doc refresh`)")
    return 0
