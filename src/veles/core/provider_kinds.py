"""How each catalogue `kind` turns an entry into an adapter (release E).

A builtin entry names one of these kinds; a user entry may use only
`openai-api` (a hosted OpenAI-compatible API) or `local` (an OpenAI-wire server
you run). Adapters import lazily — reading the catalogue must not pull every
SDK in.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from veles.core.provider import Provider
    from veles.core.providers import ModelList, ProviderContext, Wire

Entry = dict[str, Any]


@dataclass(frozen=True, slots=True)
class Kind:
    wire: Wire
    model_list: ModelList
    build: Callable[[Entry, ProviderContext], Provider]
    key_required: bool = True
    build_tool_aware: Callable[[Entry, ProviderContext], Provider] | None = None


def entry_base_url(entry: Entry) -> str | None:
    """The entry's `base_url_env` when set in the environment, else its `base_url`."""
    env = entry.get("base_url_env")
    return (os.environ.get(env) if env else None) or entry.get("base_url") or None


def _openrouter(entry: Entry, ctx: ProviderContext) -> Provider:
    from veles.adapters.openrouter import OpenRouterProvider

    # M247/M266: the constructor resolves the per-model timeout itself.
    url = entry_base_url(entry)
    if url is None:
        return OpenRouterProvider(model=ctx.model)
    return OpenRouterProvider(model=ctx.model, base_url=url)


def _openai(entry: Entry, ctx: ProviderContext) -> Provider:
    from veles.adapters.openai_direct import OpenAIProvider

    url = entry_base_url(entry)
    return OpenAIProvider() if url is None else OpenAIProvider(base_url=url)


def _anthropic(entry: Entry, ctx: ProviderContext) -> Provider:
    from veles.adapters.anthropic import AnthropicProvider

    return AnthropicProvider()


def _gemini(entry: Entry, ctx: ProviderContext) -> Provider:
    from veles.adapters.gemini import GeminiProvider

    return GeminiProvider()


def _claude_cli(entry: Entry, ctx: ProviderContext) -> Provider:
    from veles.adapters.cli.claude_cli import ClaudeCLIProvider

    # The project root, not wherever the process happens to run.
    return ClaudeCLIProvider(workdir=ctx.project.root if ctx.project else None)


def _claude_cli_tool_aware(entry: Entry, ctx: ProviderContext) -> Provider:
    """claude with Veles' tools over MCP — the config in the process's delegate dir."""
    from veles.adapters.cli.claude_cli import ClaudeCLIProvider
    from veles.adapters.cli.mcp_config import build_mcp_config

    if ctx.project is None:
        return _claude_cli(entry, ctx)
    return ClaudeCLIProvider(
        mcp_config_path=build_mcp_config(ctx.project), workdir=ctx.project.root
    )


def _codex(entry: Entry, ctx: ProviderContext) -> Provider:
    from veles.adapters.cli.codex_cli import CodexCLIProvider
    from veles.core.delegate_dir import delegate_workspace

    # Outside the project: codex reads `.codex/` layers and AGENTS.md from its cwd up.
    return CodexCLIProvider(workspace=delegate_workspace(ctx.project, "codex"))


def _codex_tool_aware(entry: Entry, ctx: ProviderContext) -> Provider:
    """codex with Veles' tools over MCP — the server passed in arguments, no file."""
    from veles.adapters.cli.codex_cli import CodexCLIProvider
    from veles.adapters.cli.mcp_config import veles_mcp_server
    from veles.core.delegate_dir import delegate_workspace

    if ctx.project is None:
        return _codex(entry, ctx)
    return CodexCLIProvider(
        workspace=delegate_workspace(ctx.project, "codex"),
        mcp_server=veles_mcp_server(ctx.project),
    )


def _ollama(entry: Entry, ctx: ProviderContext) -> Provider:
    from veles.adapters.local.ollama import OllamaProvider
    from veles.core.provider_factory import apply_local_tool_policy

    prov = OllamaProvider(base_url=entry_base_url(entry))
    apply_local_tool_policy(prov, ctx.model, str(entry.get("tools", "auto")))
    return prov


def _llamacpp(entry: Entry, ctx: ProviderContext) -> Provider:
    from veles.adapters.local.llamacpp import LlamaCppProvider
    from veles.core.provider_factory import apply_local_tool_policy

    prov = LlamaCppProvider(base_url=entry_base_url(entry))
    apply_local_tool_policy(prov, ctx.model, str(entry.get("tools", "auto")))
    return prov


def _local(entry: Entry, ctx: ProviderContext) -> Provider:
    """An OpenAI-wire server you run (vLLM, LM Studio, a gateway). Its key is
    optional: a gateway may want one, a bare server takes any."""
    from veles.adapters.local.openai_compatible import OpenAICompatibleProvider
    from veles.core.provider_factory import apply_local_tool_policy, resolve_api_key

    url = entry_base_url(entry)
    if not url:
        hint = entry.get("base_url_env") or "base_url in ~/.veles/providers.toml"
        raise RuntimeError(f"{ctx.name}: no base URL — set {hint}")
    prov = OpenAICompatibleProvider(base_url=url, api_key=resolve_api_key(ctx.name) or "local")
    prov.name = ctx.name  # `[engine.request.<id>]` and logs key on the catalogue id
    apply_local_tool_policy(prov, ctx.model, str(entry.get("tools", "auto")))
    return prov


def _openai_api(entry: Entry, ctx: ProviderContext) -> Provider:
    """A hosted OpenAI-compatible API (Groq, DeepSeek, …) — an entry, no adapter."""
    from openai import OpenAI

    from veles.core.model_budgets import resolve_max_retries, resolve_request_timeout
    from veles.core.openai_wire import CloudOpenAIProvider
    from veles.core.provider_factory import require_api_key, resolve_api_key

    url = entry_base_url(entry)
    if not url:
        raise RuntimeError(f"{ctx.name}: no base_url in ~/.veles/providers.toml")
    key = require_api_key(ctx.name) if entry.get("key_env") else resolve_api_key(ctx.name)
    kwargs: dict[str, Any] = {
        "api_key": key or "none",
        "base_url": url,
        "timeout": resolve_request_timeout(ctx.model),
    }
    retries = resolve_max_retries()
    if retries is not None:
        kwargs["max_retries"] = retries
    prov = CloudOpenAIProvider(client=OpenAI(**kwargs))
    prov.name = ctx.name
    prov.supports_tools = entry.get("tools", "auto") != "off"
    return prov


KINDS: dict[str, Kind] = {
    "openrouter": Kind("openai-wire", "cached", _openrouter),
    "openai": Kind("openai-wire", "cached", _openai),
    "anthropic": Kind("anthropic-wire", "curated", _anthropic),
    "gemini": Kind("gemini-wire", "cached", _gemini),
    "claude-cli": Kind("cli", "curated", _claude_cli, build_tool_aware=_claude_cli_tool_aware),
    "codex": Kind("cli", "live", _codex, key_required=False, build_tool_aware=_codex_tool_aware),
    "ollama": Kind("openai-wire", "live", _ollama, key_required=False),
    "llamacpp": Kind("openai-wire", "live", _llamacpp, key_required=False),
    "local": Kind("openai-wire", "live", _local, key_required=False),
    "openai-api": Kind("openai-wire", "cached", _openai_api),
}

USER_KINDS: frozenset[str] = frozenset({"openai-api", "local"})
