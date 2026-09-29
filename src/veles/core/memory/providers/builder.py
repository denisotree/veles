"""Build the external memory providers the user configured (`[memory.external.<name>]`).

Providers come from modules: a module registers a factory with
`api.add_memory_provider(name, factory)`; this builder calls it with the matching config
section. A section with no registered factory means the provider's module is not installed —
one warning per process says how to install it. A broken provider never breaks recall.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from typing import Any

_warned: set[str] = set()


def _default_config_path() -> Path:
    from veles.core.user_config import user_config_path

    return user_config_path()


def build_extra_providers(config_path: Path | None = None) -> list[object]:
    from veles.core.modules import current_module_registry

    path = config_path or _default_config_path()
    external = _external_sections(path)
    if not external:
        return []
    registry = current_module_registry()
    if registry is None:
        # No module registry at all (e.g. a command that runs without a project) —
        # nothing can ever build these providers here, so warning about missing
        # installs would just be noise every time such a command runs.
        return []
    factories = {name: factory for name, _module, factory in registry.iter_memory_providers()}
    providers: list[object] = []
    for name, section in external.items():
        factory = factories.get(name)
        if factory is None:
            _warn_once(
                name,
                f"external memory provider {name!r} is configured but its module is not "
                f"installed: `veles registry install --user {name}`",
            )
            continue
        try:
            provider = factory(section if isinstance(section, dict) else {})
        except Exception as exc:  # a broken provider must not break recall
            print(f"warning: memory provider {name!r} failed to start: {exc}", file=sys.stderr)
            continue
        if provider is not None:
            providers.append(provider)
    return providers


def _external_sections(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        print(f"warning: failed to parse {path} for external memory: {exc}", file=sys.stderr)
        return {}
    external = data.get("memory", {}).get("external", {}) if isinstance(data, dict) else {}
    return external if isinstance(external, dict) else {}


def _warn_once(key: str, message: str) -> None:
    if key in _warned:
        return
    _warned.add(key)
    print(f"warning: {message}", file=sys.stderr)


__all__ = ["build_extra_providers"]
