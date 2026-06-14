"""Rebuild this project's graphify knowledge graph.

Provisioned automatically into `<project>/.veles/tools/` when the project
declares a `graphify` MCP server (see `veles.mcp.provision`). The build's LLM
provider/model are resolved from the project's veles routing — graphify never
auto-detects a cloud backend behind your back. Edit freely; it is never
overwritten once provisioned.
"""

from __future__ import annotations

import os
import subprocess

from veles.core.context import current_project
from veles.core.risk import RiskClass
from veles.core.routing.ensemble import route
from veles.core.tools.registry import tool

# veles provider name -> graphify `--backend`
_GRAPHIFY_BACKEND = {
    "ollama": "ollama",
    "anthropic": "claude",
    "openai": "openai",
    "gemini": "gemini",
}

_BUILD_TIMEOUT_S = 1800


@tool(
    risk_class=RiskClass.PROCESS_EXECUTION,
    side_effects=["filesystem", "process"],
    timeout_s=float(_BUILD_TIMEOUT_S),
)
def graphify_rebuild(token_budget: int = 0) -> str:
    """Rebuild this project's graphify knowledge graph (graphify-out/graph.json).

    Resolves the project's LLM provider/model from veles routing and runs
    `graphify . --backend <backend> --model <model>` so the build stays on the
    configured provider (e.g. local ollama) rather than graphify's cloud
    auto-detect. `token_budget` caps the per-chunk size (default: 16000 for
    ollama — small local models overflow graphify's 60k default — and
    graphify's own default for cloud backends). Returns graphify's output tail.
    """
    project = current_project()
    if project is None:
        return "<graphify_rebuild unavailable: no active project>"

    from veles.core.model_resolver import ConfigurationError

    try:
        provider, model = route("default", project)
    except ConfigurationError as exc:
        return f"<graphify_rebuild unavailable: {exc}>"
    backend = _GRAPHIFY_BACKEND.get(provider)
    if backend is None:
        return (
            f"<graphify_rebuild: veles provider {provider!r} has no graphify "
            "backend mapping (supported: ollama, anthropic, openai, gemini)>"
        )

    budget = token_budget or (16000 if backend == "ollama" else 0)
    cmd = ["graphify", ".", "--backend", backend, "--model", model]
    if budget:
        cmd += ["--token-budget", str(budget)]

    env = dict(os.environ)
    if backend == "ollama":
        # Dummy key silences graphify's "no OLLAMA_API_KEY" warning; the
        # endpoint is local so the value is irrelevant.
        env.setdefault("OLLAMA_API_KEY", "ollama")

    try:
        result = subprocess.run(
            cmd,
            cwd=str(project.root),
            capture_output=True,
            text=True,
            timeout=_BUILD_TIMEOUT_S,
            check=False,
            env=env,
        )
    except FileNotFoundError:
        return (
            "<graphify_rebuild: `graphify` is not on PATH. Install it system-wide: "
            'uv tool install "graphifyy[mcp,ollama]">'
        )
    except subprocess.TimeoutExpired:
        return f"<graphify_rebuild: timed out after {_BUILD_TIMEOUT_S}s>"

    tail = ((result.stdout or "") + (result.stderr or ""))[-2000:]
    return f"[graphify_rebuild backend={backend} model={model}]\n{tail}\n<exit {result.returncode}>"
