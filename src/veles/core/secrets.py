"""OS-keychain-backed secret storage (Tier δ, M59-companion, OQ#4 resolved).

API keys, daemon tokens, and channel credentials used to live in plain
`.env` files. That's pragmatic but ugly: secrets end up in shell history,
in test snapshots, and (when the user forgets to `.gitignore` the file)
in commits.

This module wraps the `keyring` package — cross-platform OS keychain
(macOS Keychain, Linux Secret Service / KWallet, Windows Credential
Manager). Veles namespaces every secret under service `veles:<name>`
so multiple installations don't trip on each other and a Veles install
can be cleaned up wholesale via `keyring`'s native UIs.

The functions degrade gracefully:
  - `keyring` not installed → `ImportError` is surfaced only at the
    moment of use (lazy import).
  - Keychain access denied at the OS level → returns None / env fallback.
  - Backend not configured (some Linux CI environments) → env fallback.

`get_secret(name, env_fallback=True)` is the read-side: keychain first,
env second. Adapters can swap their `os.environ.get("OPENROUTER_API_KEY")`
calls for `get_secret("OPENROUTER_API_KEY")` and become keychain-aware
without breaking anyone whose secrets are still in `.env`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_SERVICE = "veles"

# M92: per-provider keychain naming. A key is stored at
# `veles:<provider>:<scope>` where scope = "default" for the global key
# and a project slug otherwise. Sidecar JSON tracks which scopes have
# entries because `keyring` doesn't expose enumeration cross-platform.
_DEFAULT_SCOPE = "default"
_INDEX_FILENAME = "credentials_index.json"


def _index_path() -> Path:
    """`~/.veles/credentials_index.json` — sidecar listing scoped keys.

    Resolved via `user_home()` so `VELES_USER_HOME` means the same thing
    here as everywhere else: it replaces `~`, not the `.veles` dir itself
    (pre-M158 this module treated the override as the .veles dir)."""
    from veles.core.user_paths import user_home

    return user_home() / _INDEX_FILENAME


def _load_index() -> dict[str, list[str]]:
    path = _index_path()
    if not path.is_file():
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, list[str]] = {}
    for k, v in data.items():
        if isinstance(k, str) and isinstance(v, list):
            out[k] = [s for s in v if isinstance(s, str)]
    return out


def _save_index(index: dict[str, list[str]]) -> None:
    path = _index_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _scoped_entry_name(provider: str, scope: str) -> str:
    """Keychain entry name. `<provider>:<scope>` so users can see entries
    grouped by provider in the OS keychain UI."""
    return f"{provider}:{scope}"


class KeyringUnavailable(RuntimeError):
    """Raised when no usable keyring backend can be reached."""


def _keyring() -> Any:
    """Import `keyring` lazily so test environments without it still work."""
    try:
        import keyring as _kr
        import keyring.errors as _errs
    except ImportError as exc:  # pragma: no cover — covered by pyproject pin
        raise KeyringUnavailable("`keyring` package not installed") from exc
    return _kr, _errs


def get_secret(name: str, *, env_fallback: bool = True) -> str | None:
    """Return the secret named `name`, or None when not set.

    Order: OS keychain (`veles:<name>`) first, environment second (when
    `env_fallback=True`). The two-tier read keeps existing `.env`-based
    workflows working unchanged while letting users migrate at their own pace.
    """
    try:
        kr, errs = _keyring()
    except KeyringUnavailable:
        return os.environ.get(name) if env_fallback else None
    try:
        value = kr.get_password(_SERVICE, name)
    except errs.KeyringError:
        value = None
    except Exception:
        value = None
    if isinstance(value, str):
        return value
    return os.environ.get(name) if env_fallback else None


def set_secret(name: str, value: str) -> None:
    """Persist `value` under `veles:<name>` in the OS keychain.

    Raises `KeyringUnavailable` if no backend is reachable — calls should
    catch this and offer to write to `.env` as a fallback if they want to.
    """
    kr, errs = _keyring()
    try:
        kr.set_password(_SERVICE, name, value)
    except errs.KeyringError as exc:
        raise KeyringUnavailable(f"keyring backend rejected write: {exc}") from exc


def delete_secret(name: str) -> bool:
    """Remove `veles:<name>` from the keychain. Returns True when something
    was deleted, False when no entry existed."""
    try:
        kr, errs = _keyring()
    except KeyringUnavailable:
        return False
    try:
        if kr.get_password(_SERVICE, name) is None:
            return False
        kr.delete_password(_SERVICE, name)
        return True
    except errs.PasswordDeleteError:
        return False
    except Exception:
        return False


def list_known_names() -> list[str]:
    """Return the set of names *expected* to be configured.

    Keyring's API doesn't expose enumeration cross-platform — we can't list
    every entry the user has stored. This helper returns the canonical names
    Veles itself consults, so `veles secret list` can show which are set vs.
    missing instead of crashing.
    """
    return sorted(
        {
            "OPENROUTER_API_KEY",
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "GOOGLE_API_KEY",
            "BRAVE_SEARCH_API_KEY",
            "TAVILY_API_KEY",
            "VELES_DAEMON_TOKEN",
        }
    )


# ---------------- M92: scoped provider keys ----------------


def get_provider_key(
    provider: str, *, project: str | None = None, env_fallback: bool = True
) -> str | None:
    """Resolve a provider API key respecting project scope.

    Lookup order:
      1. Keychain `veles:<provider>:<project>` (if project given).
      2. Keychain `veles:<provider>:default`.
      3. ENV vars listed in `PROVIDER_API_KEY_ENVS[provider]` (when
         `env_fallback=True`).

    Returns the first non-empty value or None.
    """
    if project:
        scoped = _read_keychain(_scoped_entry_name(provider, project))
        if scoped:
            return scoped
    default = _read_keychain(_scoped_entry_name(provider, _DEFAULT_SCOPE))
    if default:
        return default
    if env_fallback:
        return _env_for_provider(provider)
    return None


def set_provider_key(provider: str, value: str, *, project: str | None = None) -> None:
    """Persist a key under the project scope (or default if `project` is None).

    Updates the sidecar index so `list_provider_keys` can enumerate even
    when the keychain backend doesn't support listing entries.
    """
    if not value:
        raise ValueError("empty key value")
    scope = project or _DEFAULT_SCOPE
    entry = _scoped_entry_name(provider, scope)
    set_secret(entry, value)
    index = _load_index()
    scopes = index.setdefault(provider, [])
    if scope not in scopes:
        scopes.append(scope)
        scopes.sort()
        _save_index(index)


def delete_provider_key(provider: str, *, project: str | None = None) -> bool:
    """Remove a scoped key. Returns True iff a keychain entry was deleted."""
    scope = project or _DEFAULT_SCOPE
    entry = _scoped_entry_name(provider, scope)
    deleted = delete_secret(entry)
    index = _load_index()
    scopes = index.get(provider, [])
    if scope in scopes:
        scopes.remove(scope)
        if scopes:
            index[provider] = scopes
        else:
            index.pop(provider, None)
        _save_index(index)
    return deleted


def list_provider_keys(provider: str) -> list[str]:
    """Return scope names known for `provider`. Always includes scopes the
    sidecar index has recorded; the actual keychain entries may have been
    revoked out-of-band, in which case `get_provider_key(provider, project=…)`
    falls through to the next tier."""
    return list(_load_index().get(provider, []))


def list_providers_with_keys() -> dict[str, list[str]]:
    """Snapshot of every provider → its known scopes. Used by `veles secret list`
    and the wizard recap screen."""
    return _load_index()


# ---------------- helpers ----------------


def _read_keychain(name: str) -> str | None:
    """Bare keychain read without env fallback."""
    try:
        kr, errs = _keyring()
    except KeyringUnavailable:
        return None
    try:
        value = kr.get_password(_SERVICE, name)
    except errs.KeyringError:
        return None
    except Exception:
        return None
    return value if isinstance(value, str) and value else None


def _env_for_provider(provider: str) -> str | None:
    """ENV fallback honouring the canonical names in `PROVIDER_API_KEY_ENVS`.
    Imported lazily to keep `secrets.py` free of cross-package deps."""
    from veles.core.provider_factory import PROVIDER_API_KEY_ENVS

    for name in PROVIDER_API_KEY_ENVS.get(provider, ()):
        value = os.environ.get(name)
        if value:
            return value
    return None


__all__ = [
    "KeyringUnavailable",
    "delete_provider_key",
    "delete_secret",
    "get_provider_key",
    "get_secret",
    "list_known_names",
    "list_provider_keys",
    "list_providers_with_keys",
    "set_provider_key",
    "set_secret",
]
