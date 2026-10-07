"""Setting a channel up: where a platform's secrets are kept and how they are read."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from veles.core.platforms import PlatformSpec

if TYPE_CHECKING:
    from veles.core.project import Project


def secret_slot(spec: PlatformSpec, platform: str, key: str) -> str:
    """The keychain name a secret field is kept under. The platform's first
    secret field keeps the bare `<platform>` slot (a running bot's token stays
    where it always was); every other one gets `<platform>.<key>`."""
    first = next((f.key for f in spec.cred_fields if f.secret), None)
    return platform if key == first else f"{platform}.{key}"


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
        value = get_provider_key(
            secret_slot(spec, platform, f.key),
            project=project.name if project else None,
            env_fallback=False,
        )
        value = value or config.get(f.key)
        if not value and use_env and f.env:
            value = os.environ.get(f.env)
        if value:
            values[f.key] = str(value)
        elif f.required:
            missing.append(f.key)
    return values, missing


@dataclass(frozen=True, slots=True)
class ChannelStatus:
    """One enabled channel the daemon would host, and whether it is ready."""

    name: str
    state: Literal["ok", "no_module", "no_creds"]
    detail: str = ""


def channel_readiness(project: Project, session: str | None = None) -> list[ChannelStatus]:
    """Each enabled channel declared for this daemon (`[channels.*]`, or a named
    session's `[daemon.<s>.channels.*]`): does a loaded module provide its
    platform, and are its required secrets there? Synchronous, no network — the
    daemon checks this before it serves anything."""
    from veles.core.platforms import get_platform
    from veles.core.project_config import list_channel_configs, load_project_config

    out: list[ChannelStatus] = []
    declared = list_channel_configs(load_project_config(project), daemon_session=session)
    for name, block in declared:
        try:
            spec = get_platform(name)
        except KeyError:
            out.append(ChannelStatus(name, "no_module", _no_module_detail(name)))
            continue
        _, missing = resolve_secrets(spec, name, block, project=project)
        if missing:
            out.append(ChannelStatus(name, "no_creds", f"missing {', '.join(missing)}"))
        else:
            out.append(ChannelStatus(name, "ok"))
    return out


def _no_module_detail(name: str) -> str:
    """ "Isn't installed" — unless a module failed to load in this process: then its
    error, which is the real reason (the module named after the channel when there
    is one, else every failure)."""
    from veles.core.module_loading import load_failures

    failures = load_failures()
    if not failures:
        return "its module isn't installed"
    errors = [failures[name]] if name in failures else [f"{n}: {e}" for n, e in failures.items()]
    detail = "its module failed to load — " + "; ".join(errors)
    if "No module named" in detail:
        detail += (
            " — it may need a Python package: uv tool install veles-ai --with <package>"
            " (see the module's README)"
        )
    return detail


def no_channel_message(statuses: list[ChannelStatus], session: str | None) -> str:
    """Why a daemon won't start, with the command that fixes each channel."""
    suffix = f" --session {session}" if session else ""
    lines = ["error: a Veles daemon hosts channels and none is ready, so it does not start."]
    if not statuses:
        lines.append(f"  no channel is configured — connect one: `veles channel add{suffix}`")
    for s in statuses:
        if s.state == "no_module":
            fix = f"`veles registry update && veles registry install {s.name}`"
        else:
            fix = f"`veles channel add --channel {s.name}{suffix}`"
        lines.append(f"  {s.name}: {s.detail} — {fix}")
    return "\n".join(lines)


__all__ = [
    "ChannelStatus",
    "channel_readiness",
    "no_channel_message",
    "resolve_secrets",
    "secret_slot",
]
