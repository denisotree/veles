"""`veles daemon start` wizard steps (M208).

An interactive `daemon start` with no channel configured walks these steps
instead of a bare stdin `[y/N]` prompt (live 2026-07-09):

1. `DaemonBindStep` — confirm/adjust host and port (defaults come from the
   already-resolved bind cascade) and persist them to the project config
   (`[daemon]`, or `[daemon.<session>]` for a named session), mirroring what
   the project wizard's DaemonModeStep writes on a fresh project.
2. `DaemonChannelStep` — offer the registry-driven channel flow (the same
   modal collector the daemon picker's `c` and the project wizard use) and
   persist via `apply_channel`.

The steps deliberately reuse the project-wizard screens so the "pick, then
configure" shape stays identical across every daemon/channel entry point.
"""

from __future__ import annotations

from dataclasses import dataclass

from veles.core.defaults import DEFAULT_DAEMON_HOST, DEFAULT_DAEMON_PORT
from veles.core.project import Project
from veles.core.project_config import (
    load_project_config as _load_project_toml,
)
from veles.core.project_config import (
    save_project_config as _save_project_toml,
)
from veles.tui.wizard.screens.confirm import ConfirmScreen
from veles.tui.wizard.screens.input import InputScreen
from veles.tui.wizard.step import (
    WizardContext,
    WizardOutcome,
    outcome_from_dismiss,
)


async def prompt_host_port(
    ctx: WizardContext, title: str, *, host: str, port: int
) -> tuple[str, int] | WizardOutcome:
    """Ask for the daemon host and port, defaulting to `host`/`port`. A blank
    answer keeps the default and a non-numeric port falls back to it (a typo
    must not crash the wizard). Returns the navigation outcome on back/cancel."""
    host_raw = await ctx.app.push_screen_wait(
        InputScreen(title, prompt=f"Daemon host (Enter for {host})", default=host)
    )
    nav = outcome_from_dismiss(host_raw)
    if nav is not None:
        return nav
    port_raw = await ctx.app.push_screen_wait(
        InputScreen(title, prompt=f"Daemon port (Enter for {port})", default=str(port))
    )
    nav = outcome_from_dismiss(port_raw)
    if nav is not None:
        return nav
    try:
        port_clean = int((port_raw or "").strip() or port)
    except ValueError:
        port_clean = port
    return (host_raw or "").strip() or host, port_clean


@dataclass
class DaemonBindStep:
    project: Project
    session: str | None = None
    host: str = DEFAULT_DAEMON_HOST
    port: int = DEFAULT_DAEMON_PORT
    name: str = "daemon_bind"
    title: str = "Start daemon"

    async def run(self, ctx: WizardContext) -> WizardOutcome:
        answer = await prompt_host_port(ctx, self.title, host=self.host, port=self.port)
        if isinstance(answer, WizardOutcome):
            return answer
        host_clean, port_clean = answer
        ctx.answers["daemon_bind"] = {"host": host_clean, "port": port_clean}
        cfg = _load_project_toml(self.project)
        block = cfg.setdefault("daemon", {})
        if self.session:
            block = block.setdefault(self.session, {})
        block["enabled"] = True
        block["host"] = host_clean
        block["port"] = port_clean
        _save_project_toml(self.project, cfg)
        return WizardOutcome.NEXT


@dataclass
class DaemonChannelStep:
    project: Project
    session: str | None = None
    name: str = "daemon_channel"
    title: str = "Channel"

    async def run(self, ctx: WizardContext) -> WizardOutcome:
        from veles.tui.wizard.channel_flow import add_channel_via_modals

        wants = await ctx.app.push_screen_wait(
            ConfirmScreen(
                title=self.title,
                question=(
                    "No channel is connected to this daemon. Connect one now (e.g. Telegram)?"
                ),
                default=False,
            )
        )
        nav = outcome_from_dismiss(wants)
        if nav is not None:
            return nav
        if not wants:
            ctx.answers["channel"] = None
            return WizardOutcome.SKIP
        ctx.answers["channel"] = await add_channel_via_modals(
            ctx.app, self.project, session=self.session
        )
        return WizardOutcome.NEXT


def daemon_start_steps(
    project: Project,
    *,
    session: str | None,
    host: str,
    port: int,
) -> list:
    """The `veles daemon start` wizard: bind, then channel."""
    return [
        DaemonBindStep(project=project, session=session, host=host, port=port),
        DaemonChannelStep(project=project, session=session),
    ]


__all__ = ["DaemonBindStep", "DaemonChannelStep", "daemon_start_steps"]
