"""Registry tools: the agent can look up reviewed extensions and propose one.

`registry_search` reads the local registry clones only — no network. `registry_install`
runs the same install path as the CLI, including the critical-ops confirmation, so
nothing is installed without the human typing `yes`; channels without a TTY refuse.
"""

from __future__ import annotations

from veles.core.risk import RiskClass
from veles.core.tools.registry import tool


@tool(risk_class=RiskClass.SEARCH_ONLY, side_effects=[])
def registry_search(query: str = "", kind: str = "") -> str:
    """Search the connected Veles extension registries (reviewed modules, skills,
    layout packs, MCP server recipes). Use it when a task needs a capability Veles
    lacks. `kind` narrows to module|skill|layout|mcp. Returns `registry:group/name`
    references to pass to `registry_install`."""
    from veles.core.registry.catalog import search

    found, warnings = search(query, kind=kind or None, sync_missing=False)
    lines = [
        f"{f.ref}  {f.ext.version}  {f.ext.kind}  — {f.ext.description}"
        + (f"  [YANKED: {f.ext.yanked}]" if f.ext.yanked else "")
        for f in found
    ]
    if not lines:
        lines.append("(nothing found)")
    lines += [f"note: {w}" for w in warnings]
    return "\n".join(lines)


@tool(risk_class=RiskClass.PROCESS_EXECUTION, side_effects=["filesystem"])
def registry_install(name: str) -> str:
    """Install an extension from a connected registry by `name` or `registry:name`.
    The user must confirm; explain why the extension is needed before calling."""
    from veles.core.context import current_project
    from veles.core.registry.catalog import ResolveError, resolve
    from veles.core.registry.install import InstallError, install, pip_hint
    from veles.core.registry.repo import RegistryRepoError

    try:
        found = resolve(name)
        rec = install(found, project=current_project())
    except (ResolveError, InstallError, RegistryRepoError, ValueError, OSError) as exc:
        return f"not installed: {exc}"
    hint = pip_hint(found)
    return f"installed {found.ref} {rec.version}" + (f"\n{hint}" if hint else "")
