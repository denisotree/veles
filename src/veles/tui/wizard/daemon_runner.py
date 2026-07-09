"""Sync entry point for the `veles daemon start` TUI wizard (M208).

Called by `cli/commands/daemon.py::_maybe_run_start_wizard` when the start
is interactive and no channel is configured yet. Returns the answers dict
(`daemon_bind` + `channel`) on success, or None if the user cancelled —
the caller starts the daemon either way; the wizard only refines settings.
"""

from __future__ import annotations

from typing import Any

from veles.core.project import Project
from veles.tui.wizard.app import WizardApp
from veles.tui.wizard.daemon_steps import daemon_start_steps


def run_daemon_start_wizard_tui(
    project: Project,
    *,
    session: str | None,
    host: str,
    port: int,
) -> dict[str, Any] | None:
    app = WizardApp(
        steps=daemon_start_steps(project, session=session, host=host, port=port),
        title="Veles daemon setup",
    )
    return app.run()


__all__ = ["run_daemon_start_wizard_tui"]
