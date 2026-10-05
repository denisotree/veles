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


def ensure_api_key(provider: str = "openrouter", *, project: str | None = None) -> bool:
    """Check that a key is reachable for `provider`; print an error if not.

    Providers without an API key (local, CLI-delegating) always pass. The lookup
    is `core.provider_factory.has_api_key`: keychain (project scope), keychain
    (default scope), then env vars.
    """
    from veles.core.provider_factory import has_api_key
    from veles.core.providers import find_provider

    spec = find_provider(provider)
    if spec is None or not spec.needs_key:
        return True  # Task 4 turns the unknown case into a check
    if has_api_key(provider, project=project):
        return True
    envs = spec.key_env
    label = " (or ".join(envs) + ")" if len(envs) > 1 else envs[0]
    print(
        f"error: no API key for --provider {provider} "
        f"(set {label} or store via `veles secret set {provider}`)",
        file=sys.stderr,
    )
    return False
