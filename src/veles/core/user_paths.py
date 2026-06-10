"""User-scope path resolution.

`~/.veles/` is where user-global state lives: config, themes, daemon
PID/info files, daemon logs, the daemon token store, online-skills
cache, trust store, and so on. The `VELES_USER_HOME` env var overrides
`~` for tests and advanced setups (e.g. shared CI sandboxes).

Before this module five different files each rolled their own
`os.environ.get("VELES_USER_HOME")` fork — two of them re-defined a
private `_USER_HOME_ENV` constant. Centralising lets us add new
sub-directories (logs, locales, themes) without hunting through call
sites to make sure each honours the override.
"""

from __future__ import annotations

import os
from pathlib import Path

USER_HOME_ENV = "VELES_USER_HOME"


def user_home() -> Path:
    """`~/.veles/`, or `<$VELES_USER_HOME>/.veles/` when the env var
    is set. The override replaces `~` (HOME), not the `.veles`
    directory itself — keep it consistent with how user_config,
    trust_store, autopilot, and skills resolve their files.

    Does NOT create the directory — callers responsible for that
    (typically `.mkdir(parents=True, exist_ok=True)` at write time)."""
    override = os.environ.get(USER_HOME_ENV)
    base = Path(override) if override else Path.home()
    return base / ".veles"


def user_logs_dir() -> Path:
    """`~/.veles/logs/` — daemon log files live here."""
    return user_home() / "logs"


def user_themes_dir() -> Path:
    """`~/.veles/themes/` — user-installed TUI theme TOMLs."""
    return user_home() / "themes"


def user_locales_dir() -> Path:
    """`~/.veles/locales/` — user i18n overrides."""
    return user_home() / "locales"


def user_skills_dir() -> Path:
    """`~/.veles/skills/` — user-global skills (`veles skill add ...`)."""
    return user_home() / "skills"


__all__ = [
    "USER_HOME_ENV",
    "user_home",
    "user_locales_dir",
    "user_logs_dir",
    "user_skills_dir",
    "user_themes_dir",
]
