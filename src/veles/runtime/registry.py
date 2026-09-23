"""The tool surface an agent run gets, and the provider that can call it.

`load_skills` builds the per-run registry: a toolset's builtins, project and
layout skills, external MCP servers and file-based project/user tools.
`make_tool_aware_provider` builds a provider that can execute those tools
(an MCP bridge for the claude/gemini CLI delegates), and `qualify_for_provider`
rewrites tool names in a prompt to the shape such a delegate sees.
"""

from __future__ import annotations

import contextlib
import logging
import sys

from veles.core.project import Project
from veles.core.provider import Provider
from veles.core.provider_factory import make_provider
from veles.core.skills import discover_skills, make_skill_tool
from veles.core.tools import registry
from veles.core.tools.registry import Registry
from veles.core.tools.toolsets import TOOLSETS

logger = logging.getLogger(__name__)

RUN_TOOLS = TOOLSETS["run"]
INGEST_TOOLS = TOOLSETS["ingest"]
PLANNING_TOOLS = TOOLSETS["planning"]


def load_skills(
    project: Project,
    base_tools: tuple[str, ...],
    *,
    provider: Provider,
    model: str,
    skills_cache_ttl: float | None = None,
) -> Registry:
    """Build a registry exposing `base_tools` plus every project skill.

    Every discovered skill is registered into a shared `full` registry that each
    skill's handler closes over, so a skill can call another skill listed in its
    `frontmatter.tools`.

    After builtins and skills come external MCP servers (`[mcp.servers.*]`,
    mounted as `mcp_<server>_<tool>`; no MCP-SDK cost when the section is
    absent) and file-based project/user tools. Wiki-engine tools are dropped from
    `base_tools` when the layout pack does not enable the engine, so the model
    never sees their schemas.
    """
    from veles.core.layout.engines import wiki_enabled

    if wiki_enabled(project):
        # The wiki engine lives in modules/, so a non-wiki project never imports it.
        import veles.modules.wiki.tools
    else:
        gated = set(TOOLSETS.get("engine-wiki", ()))
        base_tools = tuple(t for t in base_tools if t not in gated)
    # Agent-ops command tools (job_add/…) live in a module but are always on.
    import veles.modules.agentops.tools  # noqa: F401

    skills = discover_skills(project, include_layout=True, cache_ttl=skills_cache_ttl)
    full = registry.subset(registry.list_names())
    skill_names: list[str] = []
    for skill in skills:
        try:
            entry = make_skill_tool(skill, provider=provider, model=model, base_registry=full)
            full.register(entry)
            skill_names.append(skill.name)
        except ValueError as exc:
            # Logged, not printed: the daemon log gets it, `veles run` stdout doesn't.
            logger.warning("skipping skill %r: %s", skill.name, exc)
    mcp_names: list[str] = []
    try:
        from veles.mcp.runtime import mount_mcp_tools

        mcp_names = mount_mcp_tools(full, project)
    except Exception as exc:
        logger.warning("MCP tools unavailable: %s", exc)

    return full.subset(list(base_tools) + skill_names + mcp_names + _load_file_tools(full, project))


def _load_file_tools(full: Registry, project: Project) -> list[str]:
    """Provision MCP-driven project tools, then load `<project>/.veles/tools/` and
    `~/.veles/tools/` into `full` and catalogue them. Returns the loaded names."""
    try:
        from veles.core.memory.store import local_connection
        from veles.core.tools.loader import load_into_registry
        from veles.core.user_paths import user_home
        from veles.mcp.provision import ensure_mcp_project_tools

        ensure_mcp_project_tools(project)
        # The loader still runs with `conn=None` when the database is
        # unavailable: a missing catalogue must not cost the agent its tools.
        with contextlib.ExitStack() as stack:
            conn = None
            try:
                conn = stack.enter_context(local_connection(project))
            except Exception as exc:  # pragma: no cover - catalogue is not load-bearing
                logger.warning("tool catalogue unavailable: %s", exc)
            report = load_into_registry(
                full,
                project_tools_dir=project.state_dir / "tools",
                user_tools_dir=user_home() / "tools",
                conn=conn,
            )
            if conn is not None:
                with contextlib.suppress(Exception):
                    conn.commit()
    except Exception as exc:
        logger.warning("project tools unavailable: %s", exc)
        return []
    for name, scope in report.errors:
        logger.warning("project tool %s failed to load: %s", name, scope)
    if report.unapproved:
        names = ", ".join(sorted(p.stem for p in report.unapproved))
        # Printed, not logged: an unapproved tool vanishes silently — the model
        # never sees it or a refusal — so the user must see this even when an
        # embedder has configured logging.
        print(
            f"warning: {len(report.unapproved)} self-authored tool file(s) not loaded "
            f"(unapproved): {names} — review and run `veles tool approve <name>` "
            f"(or --all) to enable them",
            file=sys.stderr,
        )
    return [lt.entry.name for lt in report.loaded]


def qualify_for_provider(prompt: str, provider: Provider, tool_names: tuple[str, ...]) -> str:
    """Rewrite short tool names to provider-specific MCP qualified names.

    claude-cli sees Veles tools as `mcp__veles__<name>` (double underscore);
    gemini-cli (with --allowed-mcp-server-names) as `mcp_veles_<name>`
    (single underscore). No-op for every other provider and for CLI delegates
    without MCP wired up.
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


def make_tool_aware_provider(
    name: str, project: Project, *, skill_model: str | None = None
) -> Provider:
    """Build a provider that can execute Veles tools.

    For `claude-cli` and `gemini-cli` this writes an MCP descriptor so the
    spawned CLI process can call our tools through the Veles MCP server;
    `skill_model` tells that server which model runs project skills.
    """
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
    # Every other provider runs plain HTTP chat and gets Veles tools through the
    # standard tool-call path; the model lets local backends detect tool support.
    return make_provider(name, model=skill_model)
