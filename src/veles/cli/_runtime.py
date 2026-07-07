"""Run-loop infrastructure shared by every agent-driven CLI verb (M46 final).

Houses the helpers that `_cmd_run`, `_cmd_ingest`, `_cmd_query`, `_cmd_lint`
and the curator's `_curate_one_session` all use to:

- Compose the system prompt with AGENTS.md + INDEX.md + memory recall
  + cache-control breakpoint (`_build_run_system_prompt`).
- Build a sliding-window history compressor on the routed `compressor`
  task (`_build_compressor`).
- Translate short tool names to the right provider's MCP-qualified shape
  (`_qualify_for_provider`).
- Construct an MCP-bridged provider for cli-delegates
  (`_make_tool_aware_provider`).
- Discover project skills + register them as additional tools
  (`_load_skills`).
- Run the agent with optional stdout streaming
  (`_run_agent_streaming_aware`).
- Manage the cumulative `TokenBudget` ContextVar across cli-delegate
  hops via `<project>/.veles/budget.state.json` (`_budget_scope`).

`cli/__init__.py` re-exports every `_<name>` so `monkeypatch.setattr(
"veles.cli._<helper>", fake)` continues to work — call sites in
extracted command bodies use lazy `from veles.cli import _foo` imports
to pick up the patched attribute at call time.
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import sys
from pathlib import Path

from veles.adapters.openrouter import OpenRouterProvider
from veles.core.agent import Agent
from veles.core.budget_state import BudgetSnapshot, save_atomic
from veles.core.budget_state import load as load_budget_snapshot
from veles.core.context import (
    TokenBudget,
    reset_budget,
    set_budget,
)
from veles.core.context_builder import assemble_system_prompt
from veles.core.context_compressor import (
    CompressionConfig,
    make_default_compressor,
)
from veles.core.memory.injector import build_memory_context_block, build_proposals_block
from veles.core.memory.router import MemoryRouter
from veles.core.project import (
    Project,
    ProjectNotFound,
    load_agents_md,
    load_project,
)
from veles.core.project_registry import Registry as ProjectRegistry
from veles.core.provider import Provider
from veles.core.provider_factory import has_api_key, make_provider
from veles.core.routing import route
from veles.core.skills import discover_skills, make_skill_tool
from veles.core.tools import registry
from veles.core.tools.registry import Registry

# M57 — toolset lists live in `core/tools/toolsets.toml` and load via
# `core.tools.toolsets.TOOLSETS`. These module-level aliases preserve the
# import paths CLI commands already depend on.
from veles.core.tools.toolsets import TOOLSETS as _TOOLSETS

logger = logging.getLogger(__name__)

# ---- shared constants ----

_INDEX_INJECTION_CAP = 8_000
_RECALL_LIMIT = 5
_RECALL_BLOCK_CHARS_CAP = 4_000

_RUN_TOOLS = _TOOLSETS["run"]
_INGEST_TOOLS = _TOOLSETS["ingest"]
_PLANNING_TOOLS = _TOOLSETS["planning"]

_DEFAULT_COMPRESS_THRESHOLD_TOKENS = 50_000


# ---- system prompt assembly ----


def _maybe_apply_project_slash_prefix(project: Project, prompt: str) -> tuple[Project, str]:
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


def _identity_header(project: Project) -> str:
    """Short instruction that pins the assistant to the active project.

    Without this, the Mind Palace incident reproduces: asked "describe
    the current project", the agent described Veles (its runtime) instead
    of the project, because the only project-shaped content in the prompt
    was an AGENTS.md template enumerating `veles ingest/query/lint`.
    Naming the project up-front and forbidding self-descriptions of the
    runtime moves the agent's default frame from "Veles assistant" to
    "<project> assistant"."""
    return (
        f"You are the assistant for the `{project.name}` project. Answer about "
        "the project's contents and the user's task. Do not describe Veles, "
        "its CLI, or its operations unless the user explicitly asks about "
        "the runtime."
    )


def _sanitize_paths(text: str, project: Project) -> str:
    """Backwards-compatible shim. The actual redaction policy lives in
    `core/sanitize` so the same rules apply at every boundary (system
    prompt, SessionStore, write_file output, SandboxViolation, daemon
    HTTP). Kept for any external caller that imported the underscored
    name; remove once nothing references it."""
    from veles.core.sanitize import sanitize

    return sanitize(text, project=project)


def build_run_system_prompt(
    project: Project,
    *,
    prompt: str = "",
    include_agents_md: bool = True,
    include_index: bool = True,
    include_proposals: bool = True,
) -> str | None:
    """Assemble the system prompt with a cache-control breakpoint.

    Stable / volatile split is centralised in `core.context_builder` (M67):
    AGENTS.md + INDEX.md are cacheable per-session, `<memory-context>` and
    `<subproject-proposals>` change every turn.

    `include_proposals=False` is for daemon/channel runs — there the
    user is talking to one specific subproject and surfacing other
    subprojects' proposals leaks scope (Mind Palace bug)."""
    stable_parts: list[str] = [_identity_header(project)]
    if include_agents_md:
        agents = load_agents_md(project)
        if agents:
            stable_parts.append(agents)
    rules = _rules_digest_block(project)
    if rules:
        stable_parts.append(rules)
    # M188: the pack's declared behavioural prompt (`prompt_file`), if any.
    # Engine-independent — placed right after AGENTS.md/rules and before the
    # wiki-gated blocks below so the cache prefix stays stable regardless of
    # which engines are on.
    layout_prompt = _load_layout_prompt(project)
    if layout_prompt:
        stable_parts.append(layout_prompt)
    # M163: the wiki-specific stable blocks (context file + RAG habits)
    # appear only when the active layout pack enables the wiki engine.
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
        # A compact map of the project root + current wiki tree, so the model
        # works with the REAL folder/page names instead of guessing. Prompt-
        # independent → stable (cached when the tree is unchanged; the whole
        # prompt is rebuilt each turn, so a mid-session move is still reflected).
        workspace = _workspace_block(project)
        if workspace:
            stable_parts.append(workspace)
        stable_parts.append(_RUN_WIKI_RAG_BLOCK)
    volatile_parts: list[str] = []
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
    stable_parts = [_sanitize_paths(p, project) for p in stable_parts]
    volatile_parts = [_sanitize_paths(p, project) for p in volatile_parts]
    sp, _stable = assemble_system_prompt(stable_parts, volatile_parts)
    return sp


def _build_run_system_prompt(args: argparse.Namespace, project: Project) -> str | None:
    """argparse-Namespace adapter over `build_run_system_prompt` — the live
    entry the CLI verbs use (`veles run`/tui), pulling the prompt + include
    flags off `args`. The public kwargs form is `build_run_system_prompt`."""
    return build_run_system_prompt(
        project,
        prompt=getattr(args, "prompt", "") or "",
        include_agents_md=not getattr(args, "no_agents_md", False),
        include_index=not getattr(args, "no_index", False),
    )


def _rules_digest_block(project: Project) -> str | None:
    """M139: the project's house-rules digest, for the stable prompt part.

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
    if not query.strip():
        return None
    # M58: open the project's SessionStore so MemoryRouter can pull from
    # `turns_fts` alongside the wiki index. Close after recall so we
    # don't leak the SQLite connection past prompt assembly.
    # M55 follow-up: ship external providers (Honcho/Mem0) when configured
    # in `~/.veles/config.toml [memory.external]`. Builder returns empty
    # when not configured; recall stays purely local in that case.
    from veles.core.memory import SessionStore
    from veles.core.memory.providers import build_extra_providers

    store = SessionStore(project.memory_db_path)
    try:
        extras = build_extra_providers()
        hits = MemoryRouter(project, store=store, extra_providers=extras).recall(
            query, limit=_RECALL_LIMIT
        )
    finally:
        store.close()
    return build_memory_context_block(hits, query, max_chars=_RECALL_BLOCK_CHARS_CAP)


_RELEVANT_PATHS_LIMIT = 8


def _relevant_paths_block(project: Project, query: str) -> str | None:
    """M118c: a compact "relevant files" block — top project_tree paths ranked
    for this turn's prompt via `relevant_semantic` (embedding-ranked when an
    embedding adapter is registered, token-ranked fallback otherwise). Volatile
    (per-turn); best-effort — any failure (no scan, store error) yields no block
    rather than breaking prompt assembly."""
    if not query.strip():
        return None
    from veles.core.memory import SessionStore
    from veles.core.project_tree import relevant_semantic

    store = SessionStore(project.memory_db_path)
    try:
        entries = relevant_semantic(store._conn, query, limit=_RELEVANT_PATHS_LIMIT)
    except Exception:
        return None
    finally:
        store.close()
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


# Bounds for the wiki-layout workspace map — kept tight because the block is
# volatile (re-sent every turn) so it reflects the agent's own moves/creates.
_WS_ROOT_LIMIT = 50
_WS_TREE_MAX_LINES = 120
_WS_TREE_DIR_CAP = 30
_WS_TREE_MAX_DEPTH = 3


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
    """Wiki-layout only: a compact map of the project ROOT (real top-level
    names) plus the current `wiki/` tree, so the model SEES what exists —
    e.g. `-- Daily --/` — instead of guessing at folder names or wrongly
    concluding "nothing found". Volatile (per-turn) so it reflects the agent's
    own moves. Best-effort: any FS error yields no block."""
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
    """M62 — surface fresh subproject proposals into the system prompt.

    Imported lazily so test fixtures that monkey-patch
    `veles.core.subproject_proposer.recent_proposals` see their override
    at call time.
    """
    from veles.core.subproject_proposer import recent_proposals

    proposals = recent_proposals(project)
    return build_proposals_block(proposals) if proposals else None


def _load_context_file(project: Project) -> str | None:
    """M163: read the layout pack's declared `context_file` (e.g. the
    wiki's INDEX.md) for stable-prompt injection. Scrubbed and capped.
    No pack / no declaration / no file → no block."""
    from veles.core.layout.discovery import find_layout
    from veles.core.safety import scan_for_injection

    pack = find_layout(project.layout_name, project)
    if pack is None or not pack.manifest.context_file:
        return None
    path = project.root / pack.manifest.context_file
    if not path.is_file():
        return None
    raw = path.read_text(encoding="utf-8", errors="replace")
    text, _ = scan_for_injection(raw, source_label=pack.manifest.context_file)
    if not text:
        return None
    if len(text) > _INDEX_INJECTION_CAP:
        text = text[:_INDEX_INJECTION_CAP] + "\n\n<truncated>"
    return text


# Legacy alias — `cli/__init__.py` re-exports `_load_index_md`.
_load_index_md = _load_context_file


def _load_layout_prompt(project: Project) -> str | None:
    """M188: read the active layout pack's declared `prompt_file` — a
    behavioural-prompt `.md` injected into the stable system prompt.

    CRITICAL DIFFERENCE from `_load_context_file`: `context_file` is read
    from the PROJECT root (a file the project itself owns, e.g. INDEX.md);
    `prompt_file` is read from the PACK ROOT (`find_layout(...).root`), so
    editing the pack's prompt reaches every existing project using it, not
    just newly-scaffolded ones. Engine-independent — no `wiki_enabled` gate;
    any pack may declare `prompt_file`. No pack / no declaration / missing
    file → no block, never an exception."""
    from veles.core.layout.discovery import find_layout
    from veles.core.safety import scan_for_injection

    pack = find_layout(project.layout_name, project)
    if pack is None or not pack.manifest.prompt_file:
        return None
    path = pack.root / pack.manifest.prompt_file
    if not path.is_file():
        return None
    raw = path.read_text(encoding="utf-8", errors="replace")
    text, _ = scan_for_injection(raw, source_label=pack.manifest.prompt_file)
    if not text:
        return None
    if len(text) > _INDEX_INJECTION_CAP:
        text = text[:_INDEX_INJECTION_CAP] + "\n\n<truncated>"
    return "Layout behaviour instructions:\n\n" + text


# ---- compressor / skills / providers ----


def build_compressor(
    project: Project,
    provider: Provider,
    *,
    no_compress: bool = False,
    compressor_model: str | None = None,
    compress_threshold_tokens: int = _DEFAULT_COMPRESS_THRESHOLD_TOKENS,
    max_summariser_input_tokens: int | None = None,
    hard_ceiling_tokens: int | None = None,
):
    """Return a HistoryCompressor for `veles run`, or None when disabled.

    M43: the summariser provider+model come from `route("compressor", project)`
    instead of being hard-pinned to OpenRouter. The CLI flag
    `--compressor-model` still wins when set explicitly. The matching
    provider's API-key env must be present; without it we now log
    a WARNING — long sessions running with no compressor will hit
    the provider's context limit, and a silent fallback hid that root
    cause in one incident already.

    Keyword-only API since M-R2.1; the unused `provider` positional
    is preserved for call-site readability ("compressor for this run's
    provider"), but the actual summariser provider is routed
    independently."""
    import logging as _logging

    _compressor_logger = _logging.getLogger("veles.core.context_compressor")
    del provider  # routed below; kept positional for caller intent.
    if no_compress:
        _compressor_logger.warning(
            "compressor disabled: --no-compress passed; long sessions "
            "will eventually hit the model context limit",
        )
        return None
    from veles.core.model_resolver import ConfigurationError

    try:
        routed_provider, routed_model = route("compressor", project)
    except ConfigurationError as exc:
        _compressor_logger.warning("compressor disabled: %s", exc)
        return None
    if not has_api_key(routed_provider):
        _compressor_logger.warning(
            "compressor disabled: no API key for routed provider %r; "
            "long sessions will eventually hit the model context limit",
            routed_provider,
        )
        return None
    model = compressor_model or routed_model
    cfg_kwargs: dict[str, int] = {"threshold_tokens": compress_threshold_tokens}
    if max_summariser_input_tokens is not None:
        cfg_kwargs["max_summariser_input_tokens"] = max_summariser_input_tokens
    if hard_ceiling_tokens is not None:
        cfg_kwargs["hard_ceiling_tokens"] = hard_ceiling_tokens
    cfg = CompressionConfig(**cfg_kwargs)
    summariser_provider = make_provider(routed_provider, model=model)
    return make_default_compressor(
        provider=summariser_provider,
        model=model,
        cfg=cfg,
        project=project,
    )


def _build_compressor(args: argparse.Namespace, project: Project, provider: Provider):
    """argparse-Namespace adapter over `build_compressor` — the live entry the
    CLI verbs use, pulling the compressor flags off `args`."""
    return build_compressor(
        project,
        provider,
        no_compress=bool(getattr(args, "no_compress", False)),
        compressor_model=getattr(args, "compressor_model", None),
        compress_threshold_tokens=int(
            getattr(args, "compress_threshold_tokens", _DEFAULT_COMPRESS_THRESHOLD_TOKENS)
        ),
    )


def _load_skills(
    project: Project,
    base_tools: tuple[str, ...],
    *,
    provider: Provider,
    model: str,
    skills_cache_ttl: float | None = None,
) -> Registry:
    """Build a registry exposing `base_tools` plus every project skill.

    Cross-skill composition: every discovered skill is registered into a
    shared `full` registry that each skill's handler closes over. When a skill
    invokes another skill listed in its `frontmatter.tools`, the lazy
    `base_registry.subset(...)` inside the handler sees it.

    M157: after builtins and skills, external MCP servers declared under
    `[mcp.servers.*]` in the project config are mounted as
    `mcp_<server>_<tool>` entries (lazy import — no-op and zero MCP-SDK
    cost when the section is absent; failures degrade to warnings).

    M163: tools owned by the wiki content engine (the `engine-wiki`
    toolset) are subtracted from `base_tools` when the project's layout
    pack doesn't enable the engine — the model never sees their schemas.
    """
    from veles.core.layout.engines import wiki_enabled

    if wiki_enabled(project):
        # Register the wiki engine's tools lazily — a non-wiki project never
        # imports the wiki module (it lives in modules/, not core; the
        # wiki-extraction refactor, 2026-06-19).
        import veles.modules.wiki.tools  # noqa: F401
    else:
        gated = set(_TOOLSETS.get("engine-wiki", ()))
        base_tools = tuple(t for t in base_tools if t not in gated)
    # M117b: include layout-pack skills (`ingest`/`query`/`lint` for the
    # default `llm-wiki`) so the runtime agent can call them by name.
    skills = discover_skills(project, include_layout=True, cache_ttl=skills_cache_ttl)
    full = registry.subset(registry.list_names())
    skill_names: list[str] = []
    for skill in skills:
        try:
            entry = make_skill_tool(skill, provider=provider, model=model, base_registry=full)
            full.register(entry)
            skill_names.append(skill.name)
        except ValueError as exc:
            # Logged (not printed) so daemon log captures the diagnostic
            # without polluting `veles run` stdout. M-R2.8.
            logger.warning("skipping skill %r: %s", skill.name, exc)
    mcp_names: list[str] = []
    try:
        from veles.mcp.runtime import mount_mcp_tools

        mcp_names = mount_mcp_tools(full, project)
    except Exception as exc:
        logger.warning("MCP tools unavailable: %s", exc)

    # M165b: provision MCP-driven project tools (e.g. graphify rebuild when a
    # `graphify` MCP server is configured), then load file-based project/user
    # tools (`<project>/.veles/tools/`, `~/.veles/tools/`) into the registry —
    # the M120 loader, previously never wired into the runtime.
    tool_names: list[str] = []
    try:
        from veles.core.tools.loader import load_into_registry
        from veles.core.user_paths import user_home
        from veles.mcp.provision import ensure_mcp_project_tools

        ensure_mcp_project_tools(project)
        report = load_into_registry(
            full,
            project_tools_dir=project.state_dir / "tools",
            user_tools_dir=user_home() / "tools",
        )
        tool_names = [lt.entry.name for lt in report.loaded]
        for name, scope in report.errors:
            logger.warning("project tool %s failed to load: %s", name, scope)
        if report.unapproved:
            names = ", ".join(sorted(p.stem for p in report.unapproved))
            logger.warning(
                "%d self-authored tool file(s) not loaded (unapproved): %s — "
                "review and run `veles tool approve <name>` (or --all) to enable them",
                len(report.unapproved),
                names,
            )
    except Exception as exc:
        logger.warning("project tools unavailable: %s", exc)

    return full.subset(list(base_tools) + skill_names + mcp_names + tool_names)


def _qualify_for_provider(prompt: str, provider: Provider, tool_names: tuple[str, ...]) -> str:
    """Rewrite short tool names to provider-specific MCP qualified names.

    claude-cli sees Veles tools as `mcp__veles__<name>` (double underscore);
    gemini-cli (with --allowed-mcp-server-names) as `mcp_veles_<name>`
    (single underscore). No-op for openrouter and for CLI delegates without
    MCP wired up.
    """
    if not provider.supports_tools:
        return prompt
    if provider.name == "claude-cli":
        from veles.adapters.cli._tool_namespace import claude_mcp_prefix, qualify_prompt

        return qualify_prompt(prompt, tool_names, prefix_fn=claude_mcp_prefix)
    if provider.name == "gemini-cli":
        from veles.adapters.cli._tool_namespace import gemini_mcp_prefix, qualify_prompt

        return qualify_prompt(prompt, tool_names, prefix_fn=gemini_mcp_prefix)
    return prompt


def _make_tool_aware_provider(
    name: str, project: Project, *, skill_model: str | None = None
) -> Provider:
    """Build a provider that can execute Veles tools.

    For `claude-cli` and `gemini-cli` this writes an MCP descriptor so the
    spawned CLI process can call our tools through the Veles MCP server.
    `skill_model` is propagated into the MCP descriptor so the child server
    knows which OpenRouter model to use when running project skills.
    """
    if name == "openrouter":
        return OpenRouterProvider()
    if name == "anthropic":
        from veles.adapters.anthropic import AnthropicProvider

        return AnthropicProvider()
    if name == "openai":
        from veles.adapters.openai_direct import OpenAIProvider

        return OpenAIProvider()
    if name == "gemini":
        from veles.adapters.gemini import GeminiProvider

        return GeminiProvider()
    if name == "claude-cli":
        from veles.adapters.cli.claude_cli import ClaudeCLIProvider
        from veles.adapters.cli.mcp_config import DEFAULT_SKILL_MODEL, build_mcp_config

        mcp_path = build_mcp_config(project, skill_model=skill_model or DEFAULT_SKILL_MODEL)
        return ClaudeCLIProvider(mcp_config_path=mcp_path)
    if name == "gemini-cli":
        from veles.adapters.cli.gemini_cli import GeminiCLIProvider
        from veles.adapters.cli.mcp_config import DEFAULT_SKILL_MODEL, build_gemini_mcp_settings

        build_gemini_mcp_settings(project, skill_model=skill_model or DEFAULT_SKILL_MODEL)
        return GeminiCLIProvider(mcp_settings_dir=project.root)
    if name in {"ollama", "llamacpp", "openai-compat"}:
        # Local providers don't bridge MCP — they run plain HTTP chat, the
        # agent loop wires Veles tools through the standard tool-call path.
        # Pass the model so tool-call support is auto-detected from the
        # model's capabilities (see provider_factory._apply_local_tool_policy);
        # VELES_LOCAL_TOOLS still forces on/off when set.
        from veles.core.provider_factory import make_provider

        return make_provider(name, model=skill_model)
    raise ValueError(f"provider {name!r} cannot bridge tools")


# ---- agent dispatch + budget ----


def _run_agent_streaming_aware(
    agent: Agent,
    prompt: str,
    args: argparse.Namespace,
    project: Project | None = None,
    *,
    emit_output: bool = True,
):
    """Run the agent, streaming chunks to stdout when args.stream is set.

    Returns (result, budget). Helper for run/ingest commands.

    `emit_output=False` (M170): run silently — no streaming, no final
    `print(result.text)`. The caller owns output. `--verify` uses this so
    the base answer isn't shown before verification can supersede it, and
    so an escalated re-run doesn't print twice.
    """
    from veles.core.trust import begin_trust_turn, end_trust_turn

    trust_turn_token = begin_trust_turn()
    try:
        if getattr(args, "stream", False) and emit_output:

            def _emit(chunk: str) -> None:
                sys.stdout.write(chunk)
                sys.stdout.flush()

            with _budget_scope(args, project=project) as budget:
                result = agent.run(prompt, on_text_delta=_emit)
            sys.stdout.write("\n")
            sys.stdout.flush()
        else:
            with _budget_scope(args, project=project) as budget:
                result = agent.run(prompt)
            if emit_output:
                print(result.text)
    finally:
        end_trust_turn(trust_turn_token)
    return result, budget


@contextlib.contextmanager
def _budget_scope(args: argparse.Namespace, project: Project | None = None):
    budget = TokenBudget(limit=getattr(args, "max_tokens_total", 0))
    token = set_budget(budget)
    snapshot_path: Path | None = None
    initial_consumed = budget.consumed
    if (
        project is not None
        and getattr(args, "provider", None) in {"claude-cli", "gemini-cli"}
        and budget.limit > 0
    ):
        snapshot_path = project.state_dir / "budget.state.json"
        save_atomic(
            snapshot_path,
            BudgetSnapshot(limit=budget.limit, consumed=initial_consumed),
        )
    try:
        yield budget
    finally:
        if snapshot_path is not None:
            snap = load_budget_snapshot(snapshot_path)
            if snap is not None:
                budget.consumed += max(0, snap.consumed - initial_consumed)
            snapshot_path.unlink(missing_ok=True)
        reset_budget(token)


def _print_run_summary(args, result, budget) -> None:
    if not args.verbose:
        return
    parts = [
        f"<finished after {result.iterations} turns",
        f"reason={result.stopped_reason}",
    ]
    if budget.limit > 0:
        parts.append(f"budget={budget.consumed}/{budget.limit}")
    print(", ".join(parts) + ">", file=sys.stderr)
