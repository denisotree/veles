"""Sync entry point for the project-level TUI wizard.

Called by `cli/project_wizard.py::maybe_run_project_wizard` when the
flow can use a Textual UI. Returns the bootstrapped `Project` on
success, or None if the user cancelled at any step.

If the wizard's DaemonModeStep collected daemon settings (host/port),
this entry point spawns `veles daemon start` in the new project root
after the wizard exits, so the user gets a running daemon (and any
configured channels — see `daemon.server._start_channel_runners`)
without an extra manual command.
"""

from __future__ import annotations

import sys
from pathlib import Path

from veles.core.project import Project
from veles.tui.wizard.app import WizardApp
from veles.tui.wizard.project_steps import project_wizard_steps


def run_project_wizard_tui(
    cwd: Path,
    *,
    skip_bootstrap_confirm: bool = False,
    autostart_daemon: bool = True,
) -> Project | None:
    """Run the project-level TUI wizard.

    `skip_bootstrap_confirm=True` is set by `maybe_run_project_wizard`
    when the preceding user-wizard already collected an affirmative
    answer to "initialize this directory?". Seeds the wizard context so
    BootstrapStep skips its duplicate ConfirmScreen.

    `autostart_daemon=False` (M129) is set when `veles daemon start` runs
    the wizard to bootstrap a missing project: that command starts the
    daemon itself afterwards, so the wizard must not spawn a second one
    (the daemon pid is a global single-instance lock).
    """
    initial = {"_skip_bootstrap_confirm": True} if skip_bootstrap_confirm else None
    app = WizardApp(steps=project_wizard_steps(cwd), initial=initial)
    answers = app.run() or {}
    project = answers.get("project")
    daemon = answers.get("daemon")
    if autostart_daemon and project is not None and isinstance(daemon, dict):
        _autostart_daemon(project, daemon)
    return project


def _autostart_daemon(project: Project, daemon: dict) -> None:
    from veles.daemon.spawn import spawn_daemon

    host = str(daemon.get("host") or "127.0.0.1")
    try:
        port = int(daemon.get("port") or 8765)
    except (TypeError, ValueError):
        port = 8765
    proc = spawn_daemon(project_root=project.root, host=host, port=port)
    if proc is None:
        print(
            f"warning: failed to spawn `veles daemon start` for {project.name}",
            file=sys.stderr,
        )
        return
    print(
        f"veles daemon spawned (pid {proc.pid}) on http://{host}:{port}/ "
        f"for project {project.name!r}",
        file=sys.stderr,
    )


__all__ = ["run_project_wizard_tui"]
