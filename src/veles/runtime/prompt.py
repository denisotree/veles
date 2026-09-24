"""System-prompt assembly for every front end that runs an agent.

`build_run_system_prompt` composes the stable part (identity, turn contract,
AGENTS.md, house rules, the layout pack's prompt, wiki index and workspace map)
and the volatile part (clock, memory recall, relevant files, proposals) around a
cache-control breakpoint (`core.context_builder`). `system_prompt_from_args` is
its argparse adapter for the CLI verbs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from veles.core.context_builder import assemble_system_prompt
from veles.core.memory.injector import build_memory_context_block, build_proposals_block
from veles.core.memory.router import MemoryRouter
from veles.core.project import Project, ProjectNotFound, load_agents_md, load_project
from veles.core.project_registry import Registry as ProjectRegistry
from veles.core.sanitize import sanitize

_INDEX_INJECTION_CAP = 8_000
_RECALL_LIMIT = 5
_RECALL_BLOCK_CHARS_CAP = 4_000
_RELEVANT_PATHS_LIMIT = 8

# Bounds for the wiki-layout workspace map.
_WS_ROOT_LIMIT = 50
_WS_TREE_MAX_LINES = 120
_WS_TREE_DIR_CAP = 30
_WS_TREE_MAX_DEPTH = 3


def apply_project_slash_prefix(project: Project, prompt: str) -> tuple[Project, str]:
    """Honor `/project <slug> <rest>` at the start of the user prompt.

    A successful match swaps `project` for the registry-resolved one and
    strips the prefix from `prompt`; an unknown slug is treated as a
    real prompt (no error — let the agent see the literal text).
    """
    if not prompt.startswith("/project "):
        return project, prompt
    parts = prompt[len("/project ") :].split(maxsplit=1)
    if not parts:
        return project, prompt
    slug = parts[0]
    rest = parts[1] if len(parts) > 1 else ""
    reg = ProjectRegistry.load()
    entry = reg.get(slug)
    if entry is None:
        print(
            f"warning: /project {slug!r} not in registry; running on cwd-resolved project instead",
            file=sys.stderr,
        )
        return project, prompt
    try:
        switched = load_project(Path(entry.path))
    except ProjectNotFound as exc:
        print(f"warning: /project {slug!r} unreadable: {exc}", file=sys.stderr)
        return project, prompt
    print(f"<switched to project '{slug}' at {entry.path}>", file=sys.stderr)
    return switched, rest or "(no further instructions; describe next task)"


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


# The turn-completion contract. The loop ends a turn the moment the model
# replies without tool calls, so a promise of deferred work ("I'll send the
# report shortly") is treated as the final answer and the work never happens.
# Complete the work in-turn, or schedule it as a reminder that fires (task_add).
_RUN_TURN_CONTRACT_BLOCK = (
    "Turn-completion contract:\n"
    "- When your turn ends, no further message is sent on its own. Do NOT end a"
    " turn with a promise of work you haven't done yet ('I'll send it shortly',"
    " 'collecting the data now', 'will follow up') — a promise in prose does not"
    " execute; the turn simply ends and nothing more is delivered.\n"
    "- If the work can be done now, finish it in this turn and put the actual"
    " result in your final message — not a description of what you're about to"
    " do.\n"
    "- If it genuinely must happen later at a specific time, schedule it with"
    " task_add (a dated reminder that reliably fires); don't promise it in prose."
)


def _identity_header(project: Project) -> str:
    """Pin the assistant to the active project.

    Without it, asked "describe the current project", the agent described
    Veles (its runtime) instead of the project. Naming the project up front
    and ruling out self-descriptions of the runtime fixes the default frame."""
    return (
        f"You are the assistant for the `{project.name}` project. Answer about "
        "the project's contents and the user's task. Do not describe Veles, "
        "its CLI, or its operations unless the user explicitly asks about "
        "the runtime."
    )


def _runtime_clock_block() -> str:
    import datetime as _dt

    now = _dt.datetime.now(tz=_dt.UTC)
    return (
        "<runtime-context>\n"
        f"Current date and time: {now.strftime('%A, %Y-%m-%d %H:%M')} UTC.\n"
        "Resolve relative dates ('tomorrow', 'on Friday', 'in an hour') "
        "against this clock.\n"
        "</runtime-context>"
    )


def build_run_system_prompt(
    project: Project,
    *,
    prompt: str = "",
    include_agents_md: bool = True,
    include_index: bool = True,
    include_proposals: bool = True,
) -> str | None:
    """Assemble the system prompt with a cache-control breakpoint.

    AGENTS.md, house rules, the pack prompt and the wiki index are the stable,
    cacheable part; the clock, `<memory-context>`, relevant files and
    `<subproject-proposals>` change every turn.

    `include_proposals=False` is for daemon/channel runs — there the user is
    talking to one specific subproject and other subprojects' proposals leak
    scope."""
    stable_parts: list[str] = [_identity_header(project), _RUN_TURN_CONTRACT_BLOCK]
    if include_agents_md:
        agents = load_agents_md(project)
        if agents:
            stable_parts.append(agents)
    rules = _rules_digest_block(project)
    if rules:
        stable_parts.append(rules)
    # The pack's behavioural prompt is engine-independent; it sits before the
    # wiki-gated blocks so the cache prefix is stable whichever engines are on.
    layout_prompt = _load_layout_prompt(project)
    if layout_prompt:
        stable_parts.append(layout_prompt)
    from veles.core.layout.engines import wiki_enabled

    wiki_on = wiki_enabled(project)
    if include_index and wiki_on:
        index = _load_context_file(project)
        if index:
            stable_parts.append(
                "Knowledge base index (read-only). "
                "Use wiki_read_page/wiki_search to explore:\n\n" + index
            )
    if wiki_on:
        # The real folder/page names, so the model does not guess them.
        workspace = _workspace_block(project)
        if workspace:
            stable_parts.append(workspace)
        stable_parts.append(_RUN_WIKI_RAG_BLOCK)
    # The clock anchors relative dates ("tomorrow at 11:00"); it is volatile, so
    # its per-minute churn never fragments the stable prefix.
    volatile_parts: list[str] = [_runtime_clock_block()]
    recall = _recall_block(project, prompt or "")
    if recall:
        volatile_parts.append(recall)
    paths = _relevant_paths_block(project, prompt or "")
    if paths:
        volatile_parts.append(paths)
    if include_proposals:
        proposals = _proposals_block(project)
        if proposals:
            volatile_parts.append(proposals)
    stable_parts = [sanitize(p, project=project) for p in stable_parts]
    volatile_parts = [sanitize(p, project=project) for p in volatile_parts]
    sp, _stable = assemble_system_prompt(stable_parts, volatile_parts)
    return sp


def system_prompt_from_args(args: argparse.Namespace, project: Project) -> str | None:
    """`build_run_system_prompt` with the prompt and include flags read off `args`."""
    return build_run_system_prompt(
        project,
        prompt=getattr(args, "prompt", "") or "",
        include_agents_md=not getattr(args, "no_agents_md", False),
        include_index=not getattr(args, "no_index", False),
    )


def _rules_digest_block(project: Project) -> str | None:
    """The project's house-rules digest, for the stable prompt part.

    Query-independent and turn-stable, so it lives next to AGENTS.md (cached)
    rather than in the per-turn `<memory-context>`. Best-effort: any DB error
    yields no block, never an exception into prompt assembly."""
    from veles.core.memory import SessionStore
    from veles.core.memory.rules_digest import build_rules_digest

    try:
        store = SessionStore(project.memory_db_path)
    except Exception:
        return None
    try:
        return build_rules_digest(store)
    except Exception:
        return None
    finally:
        store.close()


def _recall_block(project: Project, query: str) -> str | None:
    """Memory recall for this turn's prompt: session turns, insights and wiki,
    plus external providers configured in `~/.veles/config.toml [memory.external]`.

    The router gets the storage port itself, not the SQLite store behind it, so
    a project configured for a remote engine is answered by that engine."""
    if not query.strip():
        return None
    from veles.core.memory import aio
    from veles.core.memory.providers import build_extra_providers
    from veles.core.memory.store import open_store

    store = open_store(project)
    try:
        extras = build_extra_providers()
        hits = MemoryRouter(project, store=store, extra_providers=extras).recall(
            query, limit=_RECALL_LIMIT
        )
    finally:
        aio.submit(store.close())
    return build_memory_context_block(hits, query, max_chars=_RECALL_BLOCK_CHARS_CAP)


def _relevant_paths_block(project: Project, query: str) -> str | None:
    """Top project_tree paths ranked for this turn's prompt (embedding-ranked
    when an embedding adapter is registered, token-ranked otherwise).
    Best-effort — any failure yields no block rather than breaking the prompt."""
    if not query.strip():
        return None
    from veles.core.memory.store import local_connection
    from veles.core.project_tree import relevant_semantic

    try:
        with local_connection(project) as conn:
            entries = relevant_semantic(conn, query, limit=_RELEVANT_PATHS_LIMIT)
    except Exception:
        return None
    if not entries:
        return None
    lines = [
        "<relevant-files>",
        "Project paths likely relevant to this turn (ranked; read with read_file):",
    ]
    for e in entries:
        tag = f" — {e.semantic_tag}" if e.semantic_tag else ""
        lines.append(f"- `{e.rel_path}`{tag}")
    lines.append("</relevant-files>")
    return "\n".join(lines)


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


def _workspace_block(project: Project) -> str | None:
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


def _proposals_block(project: Project) -> str | None:
    """Fresh curator proposals — subproject clusters and skill promotions, each
    under its own command. Imported at call time so tests can patch the readers."""
    from veles.core.skill_promotion import recent_promote_proposals
    from veles.core.subproject_proposer import recent_proposals

    return build_proposals_block(recent_proposals(project), recent_promote_proposals(project))


def _read_pack_file(base: Path, rel: str) -> str | None:
    """A layout-pack-declared file under `base`, injection-scanned and capped.
    Missing file or nothing left after the scan → None."""
    from veles.core.safety import scan_for_injection

    path = base / rel
    if not path.is_file():
        return None
    raw = path.read_text(encoding="utf-8", errors="replace")
    text, _ = scan_for_injection(raw, source_label=rel)
    if not text:
        return None
    if len(text) > _INDEX_INJECTION_CAP:
        text = text[:_INDEX_INJECTION_CAP] + "\n\n<truncated>"
    return text


def _load_context_file(project: Project) -> str | None:
    """The pack's `context_file` (e.g. the wiki's INDEX.md), read from the
    PROJECT root — the project owns that file."""
    from veles.core.layout.discovery import find_layout

    pack = find_layout(project.layout_name, project)
    if pack is None or not pack.manifest.context_file:
        return None
    return _read_pack_file(project.root, pack.manifest.context_file)


def _load_layout_prompt(project: Project) -> str | None:
    """The pack's `prompt_file`, read from the PACK root, so editing the pack's
    prompt reaches every project using it. Engine-independent: any pack may
    declare one."""
    from veles.core.layout.discovery import find_layout

    pack = find_layout(project.layout_name, project)
    if pack is None or not pack.manifest.prompt_file:
        return None
    text = _read_pack_file(pack.root, pack.manifest.prompt_file)
    return "Layout behaviour instructions:\n\n" + text if text else None
