"""Effective provider / model resolution for entry points.

Each CLI verb gets an `argparse.Namespace` with `provider` and `model`
attributes pre-filled by argparse defaults. But the user's wizard pick
(stored in `~/.veles/config.toml`) and the project's `[provider]`
section (stored in `<project>/.veles/config.toml`) should override the
argparse defaults — otherwise picking OpenAI in the wizard but launching
`veles tui` would still boot on `openrouter` and show the wrong status.

The cascade is:

    1. `args.provider` if user passed `--provider` explicitly (≠ default).
    2. Project's `[provider] default` (e.g. wizard's project-scope pick).
    3. UserConfig.default_provider (wizard's user-scope pick).
    4. Argparse `DEFAULT_PROVIDER` (last-resort fallback).

`resolve_effective_model` does the same shape but for the model id:

    1. `args.model` if user passed `--model` explicitly (≠ default).
    2. Project's `[provider] model` (e.g. wizard's project-scope pick).
    3. Per-project persisted state from `/model` slash-command
       (tui_state.json).
    4. UserConfig.default_model.
    5. Argparse `DEFAULT_MODEL`.

The TUI and `cli/commands/daemon.py` (M130) consume both helpers, so a
daemon launched in a project without its own `[provider]` inherits the
user-level `[user] default_*` instead of dropping to `DEFAULT_MODEL`.
`cli/commands/run.py` still uses `args.provider` directly — aligning it
is a separate UX decision tracked in the R3 backlog.
"""

from __future__ import annotations

import argparse

from veles.cli._parsers._common import DEFAULT_MODEL, DEFAULT_PROVIDER
from veles.core.project import Project
from veles.core.project_config import get_section, load_project_config


def resolve_effective_provider(
    args: argparse.Namespace,
    project: Project | None,
    *,
    daemon_session: str | None = None,
) -> str:
    """Walk the cascade and return the provider Veles should boot with.

    M134: when `daemon_session` is given, a `[daemon.<name>] provider` in
    the project config takes priority over the project-wide `[provider]`
    base — so several daemon sessions in one project can each pin their own
    provider. The layer sits *below* an explicit `--provider` and *above*
    the `[provider]` default, keeping the M125/M127/M130 cascade intact."""
    explicit = getattr(args, "provider", None)
    if explicit and explicit != DEFAULT_PROVIDER:
        return explicit
    if project is not None:
        cfg = load_project_config(project)
        if daemon_session:
            ds_provider = get_section(cfg, "daemon", daemon_session).get("provider")
            if isinstance(ds_provider, str) and ds_provider:
                return ds_provider
        project_provider = get_section(cfg, "provider").get("default")
        if isinstance(project_provider, str) and project_provider:
            return project_provider
    from veles.core.user_config import load_user_config

    user_cfg = load_user_config()
    if user_cfg and user_cfg.default_provider:
        return user_cfg.default_provider
    return DEFAULT_PROVIDER


def resolve_effective_model(
    args: argparse.Namespace,
    project: Project | None,
    *,
    persisted_model: str | None = None,
    daemon_session: str | None = None,
) -> str:
    """Resolve the model id with explicit `--model` taking priority,
    then (M134) a `[daemon.<name>] model` when `daemon_session` is given,
    then the project's `[provider] model` (set by the wizard at project
    scope), then per-project persisted state (passed in by the caller
    because loading it pulls in `core/tui_state.py`), then the user
    wizard pick, then the argparse default."""
    explicit = getattr(args, "model", None)
    if explicit and explicit != DEFAULT_MODEL:
        return explicit
    if project is not None:
        cfg = load_project_config(project)
        if daemon_session:
            ds_model = get_section(cfg, "daemon", daemon_session).get("model")
            if isinstance(ds_model, str) and ds_model:
                return ds_model
        project_model = get_section(cfg, "provider").get("model")
        if isinstance(project_model, str) and project_model:
            return project_model
    if persisted_model:
        return persisted_model
    from veles.core.user_config import load_user_config

    user_cfg = load_user_config()
    if user_cfg and user_cfg.default_model:
        return user_cfg.default_model
    if explicit:
        return explicit  # the argparse default itself, but not None
    return DEFAULT_MODEL


__all__ = ["resolve_effective_model", "resolve_effective_provider"]
