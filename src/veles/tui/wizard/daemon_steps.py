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
)
from veles.tui.wizard.step import (
    outcome_from_dismiss as _nav,
)


@dataclass
class DaemonBindStep:
    project: Project
    session: str | None = None
    host: str = "127.0.0.1"
    port: int = 8765
    name: str = "daemon_bind"
    title: str = "Start daemon"

    async def run(self, ctx: WizardContext) -> WizardOutcome:
        host = await ctx.app.push_screen_wait(
            InputScreen(
                self.title,
                prompt=f"Daemon host (Enter for {self.host})",
                default=self.host,
            )
        )
        nav = _nav(host)
        if nav is not None:
            return nav
        port_raw = await ctx.app.push_screen_wait(
            InputScreen(
                self.title,
                prompt=f"Daemon port (Enter for {self.port})",
                default=str(self.port),
            )
        )
        nav = _nav(port_raw)
        if nav is not None:
            return nav
        host_clean = (host or "").strip() or self.host
        try:
            port_clean = int((port_raw or "").strip() or self.port)
        except ValueError:
            port_clean = self.port
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
        from veles.cli.channel_wizard import apply_channel
        from veles.tui.wizard.channel_flow import collect_channel_via_modals

        wants = await ctx.app.push_screen_wait(
            ConfirmScreen(
                title=self.title,
                question=(
                    "No channel is connected to this daemon. Connect one now (e.g. Telegram)?"
                ),
                default=False,
            )
        )
        nav = _nav(wants)
        if nav is not None:
            return nav
        if not wants:
            ctx.answers["channel"] = None
            return WizardOutcome.SKIP
        collected = await collect_channel_via_modals(ctx.app, title="Add channel")
        if collected is None:
            ctx.answers["channel"] = None
            return WizardOutcome.NEXT
        channel, secrets, config_fields = collected
        try:
            apply_channel(
                self.project,
                session=self.session,
                channel=channel,
                secrets=secrets,
                config_fields=config_fields,
            )
            status = "saved"
        except Exception as exc:  # keychain unavailable etc. — report, don't crash.
            status = f"failed: {type(exc).__name__}: {exc}"
        ctx.answers["channel"] = {
            "channel": channel,
            "config_fields": config_fields,
            "status": status,
        }
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
