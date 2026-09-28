"""Which registries this user has connected — `[registries.<name>]` in `~/.veles/config.toml`.

With no `[registries]` table at all the built-in `public` registry is implied; the
first add or remove writes the table out, so removing `public` sticks. Writes merge
into the raw config dict (like `persist_tui_theme`) so `[user]`, `[permissions]` and
friends survive. Access to private registries is git's business — Veles stores URLs,
never tokens.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from veles.core.io_utils import atomic_write_text, dump_toml
from veles.core.user_config import read_user_config_raw, user_config_path
from veles.core.user_paths import user_home

PUBLIC = "public"
PUBLIC_URL = "https://github.com/denisotree/veles-registry"
PRIVATE = "private"
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class RegistryConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RegistrySource:
    name: str
    url: str
    ref: str | None = None


def list_sources() -> list[RegistrySource]:
    section = read_user_config_raw().get("registries")
    if not isinstance(section, dict):
        return [RegistrySource(PUBLIC, PUBLIC_URL)]
    out: list[RegistrySource] = []
    for name, cfg in section.items():
        if not isinstance(cfg, dict):
            continue
        url, ref = cfg.get("url"), cfg.get("ref")
        if isinstance(url, str) and url:
            out.append(RegistrySource(name, url, ref if isinstance(ref, str) and ref else None))
    return out


def get_source(name: str) -> RegistrySource:
    for source in list_sources():
        if source.name == name:
            return source
    raise RegistryConfigError(f"no registry named {name!r} (see `veles registry list`)")


def add_source(url: str, *, name: str | None = None, ref: str | None = None) -> RegistrySource:
    sources = list_sources()
    taken = {s.name for s in sources}
    if name is None:
        if PRIVATE in taken:
            raise RegistryConfigError(
                f"a registry named {PRIVATE!r} already exists; pass --name for this one"
            )
        name = PRIVATE
    if not _NAME_RE.match(name):
        raise RegistryConfigError(f"registry name {name!r} must match [a-z0-9][a-z0-9-]*")
    if not url or url.startswith("-"):
        raise RegistryConfigError(f"registry url {url!r} must not be empty or start with '-'")
    if name in taken:
        raise RegistryConfigError(f"a registry named {name!r} already exists")
    source = RegistrySource(name, url, ref)
    _write([*sources, source])
    return source


def remove_source(name: str) -> None:
    sources = list_sources()
    if name not in {s.name for s in sources}:
        raise RegistryConfigError(f"no registry named {name!r}")
    _write([s for s in sources if s.name != name])
    shutil.rmtree(cache_dir(name), ignore_errors=True)


def cache_dir(name: str) -> Path:
    return user_home() / "registries" / name


def _write(sources: list[RegistrySource]) -> None:
    data = read_user_config_raw()
    data["registries"] = {
        s.name: {"url": s.url, **({"ref": s.ref} if s.ref else {})} for s in sources
    }
    path = user_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, dump_toml(data))
