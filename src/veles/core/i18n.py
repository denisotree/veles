"""Tiny extensible i18n layer.

English is canonical. Other locales translate selected keys; anything
missing falls back to English so partial translations are safe. Locales
are TOML files with namespaced tables:

    [project_wizard]
    intro_no_project = "No Veles project found at {cwd}."

Discovery order:
    1. Loaded modules' `locales/*.toml`, each under its module's name
       (a module's `hello` is `<module>.hello`).
    2. Built-in resources under `src/veles/locales/*.toml` (beat a module).
    3. User overrides under `~/.veles/locales/*.toml` (same shape).
       Same-name file wins; missing keys still fall back to built-in EN.

Active locale precedence:
    1. `VELES_LOCALE` env var.
    2. `UserConfig.language` (set in M47 first-run wizard).
    3. `"en"`.

Set once via `set_active_locale(name)`; all subsequent `t(key, **fmt)`
calls render against that locale.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from veles.core.io_utils import load_optional_toml

_DEFAULT_LOCALE = "en"
_MISSING_MARKER = "<missing: {key}>"

# Module-level state — single-process, single-locale by design (the CLI
# is short-lived; the TUI runs one user).
_active: str = _DEFAULT_LOCALE
_active_set_by_caller: bool = False
_cache: dict[tuple[str, tuple[tuple[str, Path], ...]], dict[str, str]] = {}


# ---------------- public API ----------------


def t(key: str, /, **fmt: object) -> str:
    """Render the active-locale string for `key`, formatted via str.format.

    Lookup falls back to English if the active locale doesn't define the
    key. Missing-everywhere keys return `<missing: key>` instead of
    raising — user-facing code paths must never KeyError on an i18n miss.
    """
    flat = _load(get_active_locale())
    value = flat.get(key)
    if value is None and get_active_locale() != _DEFAULT_LOCALE:
        value = _load(_DEFAULT_LOCALE).get(key)
    if value is None:
        return _MISSING_MARKER.format(key=key)
    if not fmt:
        return value
    try:
        return value.format(**fmt)
    except (KeyError, IndexError):
        # Bad format string — surface the raw template rather than crash.
        return value


def set_active_locale(name: str) -> None:
    """Override the active locale. Honours `VELES_LOCALE` env var: if set,
    it wins regardless of `name` (so a one-off invocation can force a
    locale without rewriting the user's config)."""
    global _active, _active_set_by_caller
    env = os.environ.get("VELES_LOCALE")
    _active = env or name or _DEFAULT_LOCALE
    _active_set_by_caller = True


def get_active_locale() -> str:
    """Resolve the active locale lazily on first read so tests that mutate
    the env mid-run see the right value without an explicit re-init."""
    global _active, _active_set_by_caller
    if not _active_set_by_caller:
        env = os.environ.get("VELES_LOCALE")
        if env:
            _active = env
    return _active


def reset_for_tests() -> None:
    """Clear the in-memory cache + active-locale flag so test isolation
    is straightforward. Not part of the runtime API."""
    global _active, _active_set_by_caller
    _cache.clear()
    _active = _DEFAULT_LOCALE
    _active_set_by_caller = False


# ---------------- internals ----------------


def _module_dirs() -> tuple[tuple[str, Path], ...]:
    """The loaded modules' dirs — each may ship `locales/<name>.toml`."""
    from veles.core.modules import current_module_registry

    reg = current_module_registry()
    return tuple(sorted(reg.module_dirs.items())) if reg is not None else ()


def _load(name: str) -> dict[str, str]:
    """Return the flat key→string map for `name`, caching results.

    Merged in order, later wins: each loaded module's `locales/<name>.toml`
    under the module's name (`telegram.start_greeting`), then the built-in
    locales, then the user's overrides. So core's strings beat a module's and
    the user's beat both; missing keys fall back to EN at lookup time. The cache
    is keyed on the module set too — a module loaded mid-session is seen."""
    modules = _module_dirs()
    cached = _cache.get((name, modules))
    if cached is not None:
        return cached
    merged: dict[str, str] = {}
    for module, directory in modules:
        _flatten_into(merged, load_optional_toml(directory / "locales" / f"{name}.toml"), module)
    for root in _locale_dirs():
        _flatten_into(merged, load_optional_toml(root / f"{name}.toml"))
    _cache[(name, modules)] = merged
    return merged


def _flatten_into(out: dict[str, str], data: Mapping[str, object], prefix: str = "") -> None:
    """Walk a nested TOML mapping and emit dotted keys → str leaves.

    Non-str leaves (numbers, lists, etc.) are skipped — translations are
    always strings; if you need data, put it elsewhere."""
    for key, value in data.items():
        full = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, Mapping):
            _flatten_into(out, value, full)
        elif isinstance(value, str):
            out[full] = value


def _locale_dirs() -> list[Path]:
    """Built-in dir first, then user override dir. Order matters: user
    overrides win because they're loaded second into the merged map."""
    from veles.core.user_paths import user_locales_dir

    builtin = Path(__file__).resolve().parent.parent / "locales"
    return [builtin, user_locales_dir()]


__all__ = [
    "get_active_locale",
    "reset_for_tests",
    "set_active_locale",
    "t",
]
