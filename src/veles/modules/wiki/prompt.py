"""Wiki blocks of the stable system prompt — the engine's `prompt` contribution
(moved from `runtime/prompt.py`): the pack's INDEX, the real workspace map, and
the wiki habits."""

from __future__ import annotations

from pathlib import Path

from veles.sdk import Project

from .wiki import wiki_enabled

# Bounds for the wiki-layout workspace map.
_WS_ROOT_LIMIT = 50
_WS_TREE_MAX_LINES = 120
_WS_TREE_DIR_CAP = 30
_WS_TREE_MAX_DEPTH = 3

_RUN_WIKI_RAG_BLOCK = (
    "Wiki habits (M86):\n"
    "- Before answering a knowledge question, run wiki_search with a few"
    " keywords to recall anything we've already noted on the topic. Cite"
    " matching pages by relative path.\n"
    "- When the user shares a URL or file worth keeping (an article,"
    " specification, internal doc), call wiki_ingest(source) to preserve"
    " it. Use category 'concepts'/'entities' if you can already classify"
    " it, otherwise leave the default ('sources').\n"
)


def wiki_prompt(project: Project, *, include_index: bool) -> list[str]:
    """Stable blocks, in order; none when the layout doesn't enable the engine."""
    if not wiki_enabled(project):
        return []
    from veles.sdk.layout import load_context_file

    blocks: list[str] = []
    if include_index:
        index = load_context_file(project)
        if index:
            blocks.append(
                "Knowledge base index (read-only). "
                "Use wiki_read_page/wiki_search to explore:\n\n" + index
            )
    # The real folder/page names, so the model does not guess them.
    workspace = workspace_block(project)
    if workspace:
        blocks.append(workspace)
    blocks.append(_RUN_WIKI_RAG_BLOCK)
    return blocks


def _ws_should_skip(name: str) -> bool:
    return name == ".veles" or name.startswith(".")


def _ws_list_root(root: Path) -> list[str]:
    """Flat, dirs-first listing of the project root (real top-level names)."""
    try:
        entries = sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except OSError:
        return []
    names = [f"{p.name}/" if p.is_dir() else p.name for p in entries if not _ws_should_skip(p.name)]
    if len(names) > _WS_ROOT_LIMIT:
        names = [*names[:_WS_ROOT_LIMIT], f"… (+{len(names) - _WS_ROOT_LIMIT} more)"]
    return names


def _ws_render_tree(root: Path) -> list[str]:
    """Indented, depth- and size-capped tree of `root` (dirs first)."""
    lines: list[str] = []

    def walk(d: Path, prefix: str, depth: int) -> None:
        if depth > _WS_TREE_MAX_DEPTH or len(lines) >= _WS_TREE_MAX_LINES:
            return
        try:
            entries = sorted(d.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except OSError:
            return
        entries = [p for p in entries if not _ws_should_skip(p.name)]
        shown = entries[:_WS_TREE_DIR_CAP]
        for p in shown:
            if len(lines) >= _WS_TREE_MAX_LINES:
                lines.append(f"{prefix}…")
                return
            lines.append(f"{prefix}{p.name}/" if p.is_dir() else f"{prefix}{p.name}")
            if p.is_dir():
                walk(p, prefix + "  ", depth + 1)
        if len(entries) > len(shown):
            lines.append(f"{prefix}… (+{len(entries) - len(shown)} more)")

    walk(root, "", 1)
    return lines


def workspace_block(project: Project) -> str | None:
    """Wiki-layout only: a compact map of the project root plus the current
    `wiki/` tree, so the model sees what exists instead of guessing folder names
    or concluding "nothing found". Best-effort: any FS error yields no block."""
    root = project.root
    root_names = _ws_list_root(root)
    wiki_dir = root / "wiki"
    wiki_tree = _ws_render_tree(wiki_dir) if wiki_dir.is_dir() else []
    if not root_names and not wiki_tree:
        return None
    out = [
        "<workspace>",
        "Your real workspace (wiki layout). Work with THESE paths — never invent "
        "folder names, and list/read before concluding something is missing or "
        "asking the user where things are.",
        "",
        "Project root:",
        *(f"- {n}" for n in root_names),
    ]
    if wiki_tree:
        out += ["", "Current wiki structure (`wiki/`):", *wiki_tree]
    out.append("</workspace>")
    return "\n".join(out)
