"""User-global preferences (M47) — persisted at `~/.veles/config.toml`.

VISION §7 onboarding stores the answers from the first-run wizard so
subsequent CLI invocations skip setup. Today the file holds:

    [user]
    language = "en"                  # "en" | "ru"
    default_provider = "openrouter"  # one of cli._PROVIDER_CHOICES
    first_project_name = "myorg"     # optional; recorded but not used yet

    [permissions]                    # M124-perm-unify (optional)
    fetch_url   = "approval_required"
    write_file  = "always_confirm"

Writing API keys to this file is **deliberately avoided** — keys live in
env vars only. The wizard prints a hint about which env var to set
(`OPENROUTER_API_KEY` etc.) but never persists secrets.

`VELES_USER_HOME` env override redirects `~/` for tests + advanced
setups (matches the convention used by `trust_store`, `skills`,
`project_registry`).
"""

from __future__ import annotations

import contextlib
import dataclasses
import logging
import os
import tempfile
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    _: Any  # keep Any importable for type aliases below without unused-warn

_CONFIG_FILENAME = "config.toml"


@dataclass(frozen=True, slots=True)
class UserConfig:
    language: str
    default_provider: str
    first_project_name: str | None = None
    tui_theme: str = "everforest"
    # Model the wizard recorded as the user's default. None means
    # "fall back to argparse `--model` (DEFAULT_MODEL)". Set to a
    # provider-qualified id like "openrouter/anthropic/claude-sonnet-4.6"
    # or a bare adapter-specific id like "gpt-4o".
    default_model: str | None = None


def user_config_path() -> Path:
    """Path to the user-scope config file. `VELES_USER_HOME` overrides `~`."""
    from veles.core.user_paths import user_home

    return user_home() / _CONFIG_FILENAME


def load_user_config(path: Path | None = None) -> UserConfig | None:
    """Return the saved config, or None if the file is missing / corrupt /
    malformed. Permissive: any failure falls back to None so the wizard
    can re-run on next launch instead of crashing the CLI."""
    p = path or user_config_path()
    if not p.is_file():
        return None
    try:
        with p.open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    user_section = data.get("user")
    if not isinstance(user_section, dict):
        return None
    lang = user_section.get("language")
    provider = user_section.get("default_provider")
    if not isinstance(lang, str) or not lang:
        return None
    if not isinstance(provider, str) or not provider:
        return None
    raw_proj = user_section.get("first_project_name")
    proj = raw_proj if isinstance(raw_proj, str) and raw_proj else None
    raw_theme = user_section.get("tui_theme", "everforest")
    tui_theme = raw_theme if isinstance(raw_theme, str) and raw_theme else "everforest"
    raw_model = user_section.get("default_model")
    default_model = raw_model if isinstance(raw_model, str) and raw_model else None
    return UserConfig(
        language=lang,
        default_provider=provider,
        first_project_name=proj,
        tui_theme=tui_theme,
        default_model=default_model,
    )


def save_user_config(cfg: UserConfig, path: Path | None = None) -> None:
    """Atomically write `cfg` to `~/.veles/config.toml`."""
    target = path or user_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    text = _render_toml(cfg)
    fd, tmp_name = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp_name, target)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def persist_tui_theme(theme_name: str, path: Path | None = None) -> None:
    """Persist an interactive `/theme` pick to `~/.veles/config.toml`.

    Mirrors `core.tui_state.persist_model_choice`'s best-effort semantics:
    the pick already took effect in memory (`state.theme_name` + the live
    restyle), so a transient I/O error here must not roll that back — it
    only means the choice won't survive to the next session. If the
    first-run wizard hasn't run yet (no config file), seed sane defaults
    for the other required fields so the write still succeeds."""
    cfg = load_user_config(path) or UserConfig(language="en", default_provider="openrouter")
    cfg = dataclasses.replace(cfg, tui_theme=theme_name)
    with contextlib.suppress(OSError):
        save_user_config(cfg, path)


def _render_toml(cfg: UserConfig) -> str:
    body = ["[user]"]
    fields = asdict(cfg)
    body.append(f'language = "{_escape(fields["language"])}"')
    body.append(f'default_provider = "{_escape(fields["default_provider"])}"')
    if fields["first_project_name"]:
        body.append(f'first_project_name = "{_escape(fields["first_project_name"])}"')
    body.append(f'tui_theme = "{_escape(fields["tui_theme"])}"')
    if fields.get("default_model"):
        body.append(f'default_model = "{_escape(fields["default_model"])}"')
    return "\n".join(body) + "\n"


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


# ---- raw dict access (M124-perm-unify) ----
#
# The dataclass-based `load_user_config()` above only surfaces the
# `[user]` section — the wizard's domain. New sections like
# `[permissions]` (consumed by `core/permission/policy.py`) need a
# generic raw-dict view, mirroring `core/project_config.py::load_project_config`.


def read_user_config_raw(path: Path | None = None) -> dict[str, Any]:
    """Return the full parsed TOML as a dict, or `{}` when the file is
    missing, malformed, or unreadable. Never raises.

    Malformed files log at WARNING level so a typo doesn't silently
    disable a user's `[permissions]` overrides, but the caller still
    falls back to builtin defaults rather than refuse to run."""

    p = path or user_config_path()
    if not p.is_file():
        return {}
    try:
        with p.open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        logger.warning("user config %s ignored: %s", p, exc)
        return {}
    return data if isinstance(data, dict) else {}


def get_user_section(*path: str) -> dict[str, Any]:
    """`get_section(read_user_config_raw(), *path)` — reuses the
    project-config nested-lookup helper so behaviour stays identical
    across user and project scopes."""

    from veles.core.project_config import get_section

    return get_section(read_user_config_raw(), *path)
