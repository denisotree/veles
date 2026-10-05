"""Setting a channel up: where a platform's secrets are kept and how they are read."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from veles.core.platforms import PlatformSpec

if TYPE_CHECKING:
    from veles.core.project import Project


def resolve_secrets(
    spec: PlatformSpec,
    platform: str,
    config: Mapping[str, Any],
    *,
    project: Project | None,
    use_env: bool = False,
) -> tuple[dict[str, str], list[str]]:
    """The platform's secret fields by key, and the keys of required ones that
    could not be found. Keychain first, then the channel's config block, then —
    with `use_env` (`veles channel run`) — the field's environment variable."""
    from veles.core.secrets import get_provider_key

    values: dict[str, str] = {}
    missing: list[str] = []
    for f in spec.cred_fields:
        if not f.secret:
            continue
        value = get_provider_key(platform, project=project.name if project else None)
        value = value or config.get(f.key)
        if not value and use_env and f.env:
            value = os.environ.get(f.env)
        if value:
            values[f.key] = str(value)
        elif f.required:
            missing.append(f.key)
    return values, missing


__all__ = ["resolve_secrets"]
