"""Small interactive/console checks shared by the CLI verbs."""

from __future__ import annotations

import sys


def confirm(prompt: str) -> bool:
    """Ask a y/N question on stdin; EOF counts as "no"."""
    try:
        answer = input(prompt + " ").strip().lower()
    except EOFError:
        return False
    return answer in {"y", "yes"}


def check_provider(
    provider: str, *, reason: str = "named in [engine] provider or with --provider"
) -> bool:
    """The provider exists — in the catalogue, or installed now from the user's
    registries because a flag or the config named it (`reason` says which). Prints
    why not."""
    from veles.core.providers import RETIRED, list_providers
    from veles.core.registry.ensure import ensure_provider

    if ensure_provider(provider, reason=reason):
        return True
    if provider in RETIRED:
        print(f"error: {RETIRED[provider]}", file=sys.stderr)
        return False
    print(
        f"error: unknown provider {provider!r}; available: {', '.join(list_providers())} "
        "— more from your registries: `veles registry search --kind module`",
        file=sys.stderr,
    )
    return False


def ensure_api_key(provider: str = "openrouter", *, project: str | None = None) -> bool:
    """Check that `provider` exists and a key is reachable for it; print an error if not.

    Providers without an API key (local, CLI-delegating) pass once they exist. The
    lookup is `core.provider_factory.has_api_key`: keychain (project scope),
    keychain (default scope), then env vars.
    """
    from veles.core.provider_factory import has_api_key
    from veles.core.providers import get_provider

    if not check_provider(provider):
        return False
    spec = get_provider(provider)
    if not spec.needs_key:
        return True
    if has_api_key(provider, project=project):
        return True
    envs = spec.key_env
    label = " (or ".join(envs) + ")" if len(envs) > 1 else envs[0]
    print(
        f"error: no API key for --provider {provider} "
        f"(set {label} or store via `veles secret set {envs[0]}`)",
        file=sys.stderr,
    )
    return False
