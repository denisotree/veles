"""Single loader/saver for `<project>/.veles/config.toml`.

Before this module each consumer rolled its own try/except around
`tomllib.load(...)`, and the wizard's minimal TOML emitter was buried
in `cli/project_wizard.py`. The result: four read paths, two write
paths, subtly different error handling. This module replaces them.

Schema (the wizard writes it, the daemon and TUI read it):

    [engine]
    provider = "openrouter"
    model    = "anthropic/claude-sonnet-4.6"  # optional

    [daemon]
    enabled  = true
    host     = "127.0.0.1"
    port     = 8765
    autostart = true

    [channels.telegram]
    enabled   = true
    whitelist = ["@alice", "123456"]
    chat_id   = "..."   # legacy stdin-fallback only

Unknown keys are preserved on round-trip so future fields don't get
trampled. Writes go through `io_utils.dump_toml`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from veles.core.io_utils import atomic_write_text, dump_toml, load_optional_toml
from veles.core.project import Project

_CONFIG_FILENAME = "config.toml"


def project_config_path(project: Project) -> Path:
    """Resolve the per-project config.toml location."""
    return project.state_dir / _CONFIG_FILENAME


def load_project_config(project: Project) -> dict[str, Any]:
    """Return parsed `<project>/.veles/config.toml`, or `{}` if the
    file is missing, malformed, or unreadable. Never raises."""
    return _load_config_from_path(project_config_path(project))


def _load_config_from_path(path: Path) -> dict[str, Any]:
    """Read a project config from an explicit file path. Internal —
    callers prefer `load_project_config(project)`. Exposed so the
    daemon picker (which has a `project_path` string, not a `Project`)
    can read `[engine] model` without paying to construct a Project."""
    return load_optional_toml(path)


def read_provider_model_at(project_root: Path) -> str | None:
    """Read `[engine] model` from `<project_root>/.veles/config.toml`.

    Returns `None` when the file is missing, malformed, or has no model
    key. Path-based variant of `load_project_config(...).engine.model`
    so the daemon TUI picker can show the active model per registered
    daemon without constructing a `Project` for each row."""
    cfg = _load_config_from_path(project_root / ".veles" / _CONFIG_FILENAME)
    section = cfg.get("engine")
    if not isinstance(section, dict):
        return None
    model = section.get("model")
    return model if isinstance(model, str) and model else None


def save_project_config(project: Project, data: dict[str, Any]) -> None:
    """Write `data` back to disk (atomically; the state directory is created
    if missing).

    Caller owns the diff: read → mutate → save. There's no merge step
    here on purpose — the wizard always reads first, the daemon never
    writes back, so we don't need read-modify-write locking yet."""
    atomic_write_text(project_config_path(project), dump_toml(data))


def get_section(cfg: dict[str, Any], *path: str) -> dict[str, Any]:
    """Safe nested lookup. `get_section(cfg, 'channels', 'telegram')`
    returns `cfg.get('channels', {}).get('telegram', {})`, guarding
    against non-dict values at any level."""
    cur: Any = cfg
    for key in path:
        if not isinstance(cur, dict):
            return {}
        cur = cur.get(key, {})
    return cur if isinstance(cur, dict) else {}


# ---- named daemon-session config (M134) ----

# Scalar keys under [daemon] that configure the *legacy single daemon*, not a
# named session sub-table. Used to tell `[daemon.<name>]` sub-tables apart from
# `[daemon] enabled=… host=…` flat keys.
_DAEMON_SCALAR_KEYS = frozenset(
    {"enabled", "host", "port", "autostart", "provider", "model", "mode"}
)


def list_daemon_session_names(cfg: dict[str, Any]) -> list[str]:
    """Names of declared `[daemon.<name>]` sub-tables in the project config.

    A `[daemon.<name>]` entry is a *dict* value under `[daemon]`; flat scalar
    keys (`enabled`, `host`, `port`, …) configure the legacy single daemon and
    are excluded. Returns [] when no named sessions are declared."""
    daemon = get_section(cfg, "daemon")
    return sorted(
        k for k, v in daemon.items() if isinstance(v, dict) and k not in _DAEMON_SCALAR_KEYS
    )


def get_daemon_session_config(cfg: dict[str, Any], name: str) -> dict[str, Any]:
    """Settings declared under `[daemon.<name>]` (the restart source-of-truth):
    `model`, `provider`, `host`, `port`, `mode`, plus any
    `[daemon.<name>.channels.*]`. Returns {} when the named session isn't
    declared."""
    return get_section(cfg, "daemon", name)


def list_channel_configs(
    cfg: dict[str, Any], *, daemon_session: str | None = None
) -> list[tuple[str, dict[str, Any]]]:
    """Enabled channel declarations as `(platform, channel_cfg)` pairs (M136).

    Channels bind to a runtime session: when `daemon_session` is given the
    source is `[daemon.<name>.channels.<type>]` (the named session reads ONLY
    its own channels, so two sessions never double-bind one bot); otherwise the
    legacy global `[channels.<type>]` for the unnamed daemon. Only entries whose
    `enabled` is truthy are returned, sorted by platform for determinism."""
    if daemon_session:
        channels = get_section(cfg, "daemon", daemon_session, "channels")
    else:
        channels = get_section(cfg, "channels")
    out: list[tuple[str, dict[str, Any]]] = []
    for platform, pcfg in channels.items():
        if isinstance(pcfg, dict) and pcfg.get("enabled"):
            out.append((platform, pcfg))
    out.sort(key=lambda pair: pair[0])
    return out


__all__ = [
    "get_section",
    "load_project_config",
    "project_config_path",
    "read_provider_model_at",
    "save_project_config",
]
