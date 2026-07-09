"""Provider factory — build a chat-only `Provider` from a CLI provider name.

Extracted from `cli.py` in M44 so builtin tools (notably `advisor_review`)
can spawn sub-agents on a routed `(provider, model)` pair without an
import cycle through the CLI layer. Tool-aware providers (with MCP
bridging for cli-delegates) still live in `cli.py` since they need
project-scoped MCP-config wiring.

Direct-API providers (`openrouter`, `anthropic`, `openai`, `gemini`)
take their API key from environment variables listed in
`PROVIDER_API_KEY_ENVS`. cli-delegate providers (`claude-cli`,
`gemini-cli`) authenticate through their own binary's auth state and
return False from `has_api_key` since they cannot drive arbitrary
chat-only sub-agents.

Local-model providers (`ollama`, `llamacpp`, `openai-compat`) introduced
in M78 don't need any credentials; `has_api_key` returns True for them
unconditionally so the agent loop doesn't gate them behind a key check.
Tool calling is **auto-detected** from the model's advertised capabilities
(ollama `/api/show` reports `capabilities: ["tools", ...]`): pass the model
to `make_provider(name, model=...)` and tools turn on iff the model speaks
the OpenAI tool-call format. `VELES_LOCAL_TOOLS=1|0` remains an explicit
override (force on/off) when set; unset means auto-detect.
"""

from __future__ import annotations

import os

from veles.core.provider import Provider

PROVIDER_API_KEY_ENVS: dict[str, tuple[str, ...]] = {
    "openrouter": ("OPENROUTER_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
}

LOCAL_PROVIDERS: frozenset[str] = frozenset({"ollama", "llamacpp", "openai-compat"})


def _local_tools_override() -> bool | None:
    """Explicit `VELES_LOCAL_TOOLS` override, or None to auto-detect.

    Returns True/False when the env var is set to a recognised truthy/falsy
    value (force tool calling on/off), or None when unset — in which case the
    factory auto-detects from the model's advertised capabilities."""
    raw = os.environ.get("VELES_LOCAL_TOOLS", "").strip().lower()
    if raw == "":
        return None
    return raw in {"1", "true", "yes", "on"}


def _apply_local_tool_policy(provider: Provider, model: str | None) -> None:
    """Set `provider.supports_tools` for a freshly-built local provider.

    An explicit `VELES_LOCAL_TOOLS` value wins (force on/off). Otherwise
    auto-detect: when the provider can probe a model's capabilities (ollama
    exposes `model_supports_tools` via `/api/show`) and the model is known,
    enable tools iff the model advertises them. When the capability can't be
    determined (no probe, no model, or probe error) default to off — a
    tool-blind model that's handed tool schemas can stall the agent loop."""
    override = _local_tools_override()
    if override is not None:
        provider.supports_tools = override
        return
    detect = getattr(provider, "model_supports_tools", None)
    if callable(detect) and model:
        try:
            provider.supports_tools = bool(detect(model))
        except Exception:
            provider.supports_tools = False
    else:
        provider.supports_tools = False


def make_provider(name: str, model: str | None = None) -> Provider:
    """Build a chat-only provider (no MCP bridging) from its CLI name.

    `model` (when given) lets local providers auto-detect tool-call support
    from the model's advertised capabilities — see `_apply_local_tool_policy`.
    """
    if name == "openrouter":
        from veles.adapters.openrouter import OpenRouterProvider

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

        return ClaudeCLIProvider()
    if name == "gemini-cli":
        from veles.adapters.cli.gemini_cli import GeminiCLIProvider

        return GeminiCLIProvider()
    if name == "ollama":
        from veles.adapters.local.ollama import OllamaProvider

        prov: Provider = OllamaProvider()
        _apply_local_tool_policy(prov, model)
        return prov
    if name == "llamacpp":
        from veles.adapters.local.llamacpp import LlamaCppProvider

        prov = LlamaCppProvider()
        _apply_local_tool_policy(prov, model)
        return prov
    if name == "openai-compat":
        from veles.adapters.local.openai_compatible import OpenAICompatibleProvider

        prov = OpenAICompatibleProvider()
        _apply_local_tool_policy(prov, model)
        return prov
    raise ValueError(f"unknown provider: {name!r}")


def has_api_key(provider_name: str, *, project: str | None = None) -> bool:
    """Return True iff a key is available for a direct-API provider.

    M92: lookup is delegated to `core.secrets.get_provider_key` which
    consults keychain `veles:<provider>:<project>`, then `veles:<provider>:default`,
    then ENV. cli-delegate providers (`claude-cli`, `gemini-cli`) return
    False — they authenticate via their own binary and can't power
    chat-only sub-agents. Local-model providers (`ollama`, `llamacpp`,
    `openai-compat`) return True unconditionally — they don't authenticate.
    """
    if provider_name in LOCAL_PROVIDERS:
        return True
    if provider_name not in PROVIDER_API_KEY_ENVS:
        return False
    from veles.core.secrets import get_provider_key

    return get_provider_key(provider_name, project=project) is not None


def require_api_key(
    provider_name: str,
    *,
    explicit: str | None = None,
    env_hint: str | None = None,
) -> str:
    """`resolve_api_key` + raise on miss with a consistent message.

    Every direct-API adapter used to repeat the same three-liner in its
    `__init__`: resolve, check for None, raise RuntimeError. The error
    string drifted (some said "set $X", some said "configure via
    wizard") and the env var hint was sometimes wrong. Single helper
    keeps the message stable and the call site to one line."""
    key = resolve_api_key(provider_name, explicit=explicit)
    if key:
        return key
    envs = PROVIDER_API_KEY_ENVS.get(provider_name, ())
    hint = env_hint or (envs[0] if envs else "")
    if hint:
        raise RuntimeError(
            f"no API key configured for provider {provider_name!r}. "
            f"Set ${hint}, configure it via bare `veles` (first-run wizard) or "
            f"`veles secret add {provider_name}`."
        )
    raise RuntimeError(f"no API key configured for provider {provider_name!r}.")


def resolve_api_key(provider_name: str, *, explicit: str | None = None) -> str | None:
    """Adapter-facing resolver: explicit arg → keychain (active project) → keychain (default) → env.

    Used by every direct-API adapter (`openrouter`, `anthropic`, `openai`,
    `gemini`) so a key saved via the project wizard's keychain flow
    (M92/M100) reaches the provider without the user having to export
    an env var. Returns None if nothing is configured — the caller
    raises a typed error so it surfaces in the usual place.
    """
    if explicit:
        return explicit
    project_name: str | None = None
    try:
        from veles.core.context import current_project

        proj = current_project()
        if proj is not None:
            project_name = proj.name
    except Exception:
        project_name = None
    from veles.core.secrets import get_provider_key

    return get_provider_key(provider_name, project=project_name)
