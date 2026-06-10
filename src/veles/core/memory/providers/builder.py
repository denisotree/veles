"""Factory for external memory providers (Tier δ, M55 follow-up).

`build_extra_providers()` reads the user's `~/.veles/config.toml` for a
`[memory.external]` section and constructs the configured adapters. The
return value plugs directly into `MemoryRouter(extra_providers=...)`.

Config shape (everything under `[memory.external]` is optional):

    [memory.external.honcho]
    api_key  = "..."
    app_id   = "..."
    user_id  = "denisotree"
    base_url = "https://demo.honcho.dev"   # optional

    [memory.external.mem0]
    api_key  = "..."
    user_id  = "denisotree"
    agent_id = "veles"                     # optional

Missing keys for an adapter → that adapter is skipped (no exception).
Missing config file → empty list (current behaviour preserved).
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from typing import Any

from veles.core.memory.providers.honcho import HonchoMemoryProvider
from veles.core.memory.providers.mem0 import Mem0MemoryProvider
from veles.core.memory.providers.supermemory import SupermemoryProvider


def _default_config_path() -> Path:
    from veles.core.user_config import user_config_path

    return user_config_path()


def build_extra_providers(config_path: Path | None = None) -> list[object]:
    """Construct configured external memory providers.

    Returns a list of provider objects (duck-typed against `MemoryProvider`).
    Empty list when no config is present or no provider section is filled.
    """
    path = config_path or _default_config_path()
    if not path.exists():
        return []
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        print(
            f"warning: failed to parse {path} for external memory: {exc}",
            file=sys.stderr,
        )
        return []
    external = (
        data.get("memory", {}).get("external", {}) if isinstance(data, dict) else {}
    )
    if not isinstance(external, dict):
        return []
    providers: list[object] = []
    honcho = _build_honcho(external.get("honcho"))
    if honcho is not None:
        providers.append(honcho)
    mem0 = _build_mem0(external.get("mem0"))
    if mem0 is not None:
        providers.append(mem0)
    supermem = _build_supermemory(external.get("supermemory"))
    if supermem is not None:
        providers.append(supermem)
    return providers


def _build_honcho(cfg: Any) -> HonchoMemoryProvider | None:
    if not isinstance(cfg, dict):
        return None
    api_key = cfg.get("api_key")
    app_id = cfg.get("app_id")
    user_id = cfg.get("user_id")
    if not (api_key and app_id and user_id):
        return None
    return HonchoMemoryProvider(
        api_key=str(api_key),
        app_id=str(app_id),
        user_id=str(user_id),
        base_url=str(cfg["base_url"]) if cfg.get("base_url") else None,
    )


def _build_mem0(cfg: Any) -> Mem0MemoryProvider | None:
    if not isinstance(cfg, dict):
        return None
    api_key = cfg.get("api_key")
    user_id = cfg.get("user_id")
    if not (api_key and user_id):
        return None
    return Mem0MemoryProvider(
        api_key=str(api_key),
        user_id=str(user_id),
        agent_id=str(cfg["agent_id"]) if cfg.get("agent_id") else None,
    )


def _build_supermemory(cfg: Any) -> SupermemoryProvider | None:
    if not isinstance(cfg, dict):
        return None
    api_key = cfg.get("api_key")
    if not api_key:
        return None
    return SupermemoryProvider(
        api_key=str(api_key),
        user_id=str(cfg["user_id"]) if cfg.get("user_id") else None,
    )


__all__ = ["build_extra_providers"]
