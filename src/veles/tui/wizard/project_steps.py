"""Concrete steps for the project-level TUI wizard.

Run after the user wizard (or whenever cwd has no `.veles/project.toml`).
Bootstrap is the gate — declining cancels the whole flow. Subsequent
steps are independent and skippable.

Step order:
    1. Layout picker        (M162: BEFORE bootstrap, so init_project
                             scaffolds the chosen pack; auto-skips when
                             only one pack is installed)
    2. Bootstrap            (confirm → init_project(layout=picked))
    3. Provider override    (optional; per-project API-key flow)
    4. Daemon mode          (optional; if accepted → host/port + a channel
                             via the shared registry-driven flow; else skipped)
    5. Recap                (always shown)

There is no AGENTS.md-normalization step: `init_project` itself folds an
existing CLAUDE.md/GEMINI.md into AGENTS.md without loss (M272), so by the time
bootstrap returns there is nothing left to reconcile.

The old "wiki seed" step (bulk-copy README/docs into sources/seed/) was removed:
content enters the wiki only via content-aware `veles add`, which distils each
source into topical pages and relocates the raw — a blind bulk copy just made a
redundant, unstructured pile.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from veles.core.defaults import DEFAULT_DAEMON_HOST, DEFAULT_DAEMON_PORT
from veles.core.i18n import t
from veles.core.project import Project, ProjectAlreadyExists, init_project, load_project
from veles.core.project_config import (
    load_project_config as _load_project_toml,
)
from veles.core.project_config import (
    save_project_config as _save_project_toml,
)
from veles.tui.wizard.screens import (
    ChoiceScreen,
    ConfirmScreen,
    InputScreen,
    ProgressScreen,
)
from veles.tui.wizard.screens.choice import ChoiceItem
from veles.tui.wizard.step import (
    CANCEL_SENTINEL as _CANCEL_SENTINEL,
)
from veles.tui.wizard.step import (
    WizardContext,
    WizardOutcome,
    outcome_from_dismiss,
)


def _provider_choices() -> list[ChoiceItem]:
    # The project picker keeps labels compact — taglines were in the first-run wizard.
    # Registry offers follow the catalogue and install on pick.
    from veles.core.providers import find_provider
    from veles.core.registry import ensure

    items = []
    for n in ensure.available_providers():
        spec = find_provider(n)
        items.append(ChoiceItem(label=spec.label if spec else f"{n} (registry)", value=n))
    return items


# ---------------- Step 1: Bootstrap ----------------


@dataclass
class BootstrapStep:
    """Confirm + run init_project. This step gates the whole wizard:
    declining returns CANCEL and the runner unwinds."""

    cwd: Path
    name: str = "bootstrap"
    title: str = "Initialize Veles project"

    async def run(self, ctx: WizardContext) -> WizardOutcome:
        from veles.core.layout import LAYOUT_DEFAULT

        layout = ctx.answers.get("layout") or LAYOUT_DEFAULT
        # If the preceding user-wizard already asked "initialize here?" and
        # got a Yes, skip the duplicate confirm and go straight to init —
        # otherwise the user has to answer the same question twice (the
        # screen flashes for a moment, then re-appears identical).
        if ctx.answers.get("_skip_bootstrap_confirm"):
            try:
                project = init_project(self.cwd, name=None, force=False, layout=layout)
            except ProjectAlreadyExists:
                project = load_project(self.cwd)
            ctx.answers["project"] = project
            ctx.answers["bootstrap_status"] = "created"
            return WizardOutcome.NEXT

        result = await ctx.app.push_screen_wait(
            ConfirmScreen(
                title=self.title,
                question=t("project_wizard.ask_initialize"),
                default=True,
            )
        )
        nav = outcome_from_dismiss(result)
        if nav is not None:
            return nav
        if not result:
            return WizardOutcome.CANCEL
        try:
            project = init_project(self.cwd, name=None, force=False, layout=layout)
        except ProjectAlreadyExists:
            project = load_project(self.cwd)
        ctx.answers["project"] = project
        ctx.answers["bootstrap_status"] = "created"
        return WizardOutcome.NEXT


# ---------------- Step 2: Provider override ----------------


@dataclass
class ProviderOverrideStep:
    """Optional project-scoped provider/model + API key. Reuses the
    same keychain scope mechanism as user-level (M92), but the chosen
    key lives under `veles:<provider>:<project-slug>`."""

    name: str = "provider_override"
    title: str = "Project provider override"

    async def run(self, ctx: WizardContext) -> WizardOutcome:
        wants = await ctx.app.push_screen_wait(
            ConfirmScreen(
                title=self.title,
                question=t("project_wizard.ask_provider_override"),
                default=False,
            )
        )
        nav = outcome_from_dismiss(wants)
        if nav is not None:
            return nav
        if not wants:
            ctx.answers["provider_override"] = None
            return WizardOutcome.SKIP

        # Default the picker to whatever the user-level config picked,
        # otherwise openrouter — minimises clicks for the common
        # "same provider, different key" case.
        from veles.core.user_config import load_user_config

        user_cfg = load_user_config()
        default_provider = (user_cfg.default_provider if user_cfg else None) or "openrouter"
        picked = await ctx.app.push_screen_wait(
            ChoiceScreen(
                title=self.title,
                items=_provider_choices(),
                subtitle=t("project_wizard.ask_provider_label"),
                default=default_provider,
            )
        )
        nav = outcome_from_dismiss(picked)
        if nav is not None:
            return nav
        from veles.tui.wizard.user_steps import install_picked_provider

        if not await install_picked_provider(ctx, picked):
            return WizardOutcome.BACK

        project: Project = ctx.answers["project"]
        # Configure the API key for this project scope first, so the
        # model picker that follows actually sees the project's key.
        await _project_api_key_flow(ctx, project, picked)

        # Now fetch the available models with that key (or the inherited
        # default for `not-required` providers).
        picked_model = await _pick_project_model(
            ctx, picked, default_pref=user_cfg.default_model if user_cfg else None
        )

        cfg = _load_project_toml(project)
        cfg.setdefault("engine", {})
        cfg["engine"]["provider"] = picked
        if picked_model:
            cfg["engine"]["model"] = picked_model
        _save_project_toml(project, cfg)
        ctx.answers["provider_override"] = {
            "provider": picked,
            "model": picked_model,
        }
        return WizardOutcome.NEXT


async def _pick_project_model(
    ctx: WizardContext, provider: str, *, default_pref: str | None
) -> str | None:
    """Mirror of user-level ModelStep, scoped to the project."""
    from veles.cli.repl.model_fetcher import validate_and_fetch_models
    from veles.core.provider_factory import needs_api_key
    from veles.core.secrets import get_provider_key
    from veles.tui.wizard.user_steps import ask_model_id, model_choice_screen

    project: Project = ctx.answers["project"]
    slug = project.name
    if not needs_api_key(provider):
        api_key = "local"
    else:
        api_key = get_provider_key(provider, project=slug) or ""
        if not api_key:
            return None

    status, models, error = await asyncio.to_thread(validate_and_fetch_models, provider, api_key)
    screen = model_choice_screen(
        "Project model override", provider, models if status == "ok" else [], default=default_pref
    )
    if screen is None:
        if status != "unreachable":
            return None
        typed = await ask_model_id(ctx, "Project model override", error)
        return str(typed).strip() or None if isinstance(typed, str) else None
    result = await ctx.app.push_screen_wait(screen)
    if result is None or result == _CANCEL_SENTINEL:
        return None
    return str(result)


async def _project_api_key_flow(ctx: WizardContext, project: Project, provider: str) -> None:
    """Same shape as user-level ApiKeyStep but writes to the project scope."""
    from veles.core.provider_factory import env_api_key, needs_api_key
    from veles.core.secrets import (
        KeyringUnavailable,
        get_provider_key,
        set_provider_key,
    )

    if not needs_api_key(provider):
        ctx.answers["project_api_key_status"] = "not-required"
        return

    slug = project.name
    default_key = get_provider_key(provider, env_fallback=False)
    env_name, env_value = env_api_key(provider) or (None, None)

    options: list[ChoiceItem] = []
    if default_key:
        options.append(ChoiceItem("Inherit the default keychain key", "inherit"))
    if env_value:
        label = f"Use ENV value ({env_name})"
        options.append(ChoiceItem(label, "env"))
    options.append(ChoiceItem("Enter a project-specific key", "input"))
    options.append(ChoiceItem("Skip — configure later", "skip"))

    choice = await ctx.app.push_screen_wait(
        ChoiceScreen(
            title="Project API key",
            items=options,
            subtitle=f"What should `{slug}` use for {provider}?",
            default=options[0].value,
        )
    )
    if choice is None or choice in (_CANCEL_SENTINEL, "skip"):
        ctx.answers["project_api_key_status"] = "deferred"
        return
    if choice == "inherit":
        ctx.answers["project_api_key_status"] = "inherited-default"
        return
    if choice == "env":
        # Pin the env value into the project scope so it's stable across env changes.
        try:
            set_provider_key(provider, env_value or "", project=slug)
            ctx.answers["project_api_key_status"] = "saved-from-env"
        except KeyringUnavailable as exc:
            ctx.answers["project_api_key_status"] = f"keychain-unavailable: {exc}"
        return
    # input
    entered = await ctx.app.push_screen_wait(
        InputScreen(
            title="Project API key",
            prompt=f"Paste the {provider} key for `{slug}`. Stored in the OS keychain.",
            password=True,
        )
    )
    if entered is None or entered == _CANCEL_SENTINEL or not entered.strip():
        ctx.answers["project_api_key_status"] = "deferred"
        return
    try:
        set_provider_key(provider, entered.strip(), project=slug)
        ctx.answers["project_api_key_status"] = "saved-new"
    except KeyringUnavailable as exc:
        ctx.answers["project_api_key_status"] = f"keychain-unavailable: {exc}"


# ---------------- Step 4: Daemon mode + channel ----------------


@dataclass
class DaemonModeStep:
    name: str = "daemon_mode"
    title: str = "Run as a daemon"

    async def run(self, ctx: WizardContext) -> WizardOutcome:
        wants = await ctx.app.push_screen_wait(
            ConfirmScreen(
                title=self.title,
                question=(
                    "Run this project as a long-lived daemon? "
                    "A daemon enables `veles daemon` picker control, "
                    "remote sessions, and channel integration."
                ),
                default=False,
            )
        )
        nav = outcome_from_dismiss(wants)
        if nav is not None:
            return nav
        if not wants:
            ctx.answers["daemon"] = None
            return WizardOutcome.SKIP

        from veles.tui.wizard.daemon_steps import prompt_host_port

        answer = await prompt_host_port(
            ctx, self.title, host=DEFAULT_DAEMON_HOST, port=DEFAULT_DAEMON_PORT
        )
        if isinstance(answer, WizardOutcome):
            return answer
        host_clean, port_clean = answer
        ctx.answers["daemon"] = {
            "host": host_clean,
            "port": port_clean,
            "autostart": True,
        }
        project: Project = ctx.answers["project"]
        cfg = _load_project_toml(project)
        cfg.setdefault("daemon", {})
        cfg["daemon"]["enabled"] = True
        cfg["daemon"]["host"] = host_clean
        cfg["daemon"]["port"] = port_clean
        cfg["daemon"]["autostart"] = True
        _save_project_toml(project, cfg)
        await _channel_subflow(ctx)
        return WizardOutcome.NEXT


async def _channel_subflow(ctx: WizardContext) -> None:
    """Registry-driven channel sub-flow (M172). Asks whether to add a channel,
    then runs the shared pick-type → collect-creds modal flow
    (`wizard/channel_flow.py`, the same one the daemon picker's `c` uses) and
    persists via `apply_channel`. No telegram hardcoded — the channel-type
    choice is always shown so new platforms appear with zero wizard code."""
    from veles.tui.wizard.channel_flow import add_channel_via_modals

    wants = await ctx.app.push_screen_wait(
        ConfirmScreen(
            title="Channel",
            question=t("project_wizard.ask_channel"),
            default=False,
        )
    )
    if not wants or wants == _CANCEL_SENTINEL:
        ctx.answers["channel"] = None
        return
    ctx.answers["channel"] = await add_channel_via_modals(
        ctx.app, ctx.answers["project"], session=None
    )


# ---------------- Step 6: Recap ----------------


@dataclass
class RecapStep:
    name: str = "recap"
    title: str = "All done"
    lines_acc: list[str] = field(default_factory=list)

    async def run(self, ctx: WizardContext) -> WizardOutcome:
        project: Project = ctx.answers["project"]
        lines = [f"  · project '{project.name}' at {project.root}"]
        if ctx.answers.get("provider_override"):
            ov = ctx.answers["provider_override"]
            model = ov["model"] or "<inherit-model>"
            lines.append(f"  · provider override: {ov['provider']}/{model}")
        d = ctx.answers.get("daemon")
        if d:
            lines.append(f"  · daemon: {d['host']}:{d['port']}")
        ch = ctx.answers.get("channel")
        if ch:
            lines.append(f"  · channel: {ch['channel']} ({ch['status']})")
        await ctx.app.push_screen_wait(ProgressScreen(title=self.title, lines=lines))
        return WizardOutcome.NEXT


def project_wizard_steps(cwd: Path) -> list:
    return [
        LayoutPickerStep(),
        BootstrapStep(cwd=cwd),
        ProviderOverrideStep(),
        DaemonModeStep(),
        RecapStep(),
    ]


# ---------------- LayoutPickerStep ----------------


@dataclass
class LayoutPickerStep:
    """Pick the project's content layout-pack (default `bare`).

    M162: runs BEFORE BootstrapStep so `init_project(layout=...)`
    scaffolds exactly what the chosen pack declares — no post-hoc
    project.toml rewrite, no leftover skeleton from the default pack.
    Single-pack installations auto-confirm without showing the screen.
    Installed packs and the layouts in the cached registries are listed;
    picking a registry one installs it with the terminal handed back
    (`App.suspend`, for the normal install confirmation), falling back to
    the default when it can't be had.
    """

    name: str = "layout-picker"
    title: str = "Pick a content layout"

    async def run(self, ctx: WizardContext) -> WizardOutcome:
        from veles.core.layout import LAYOUT_DEFAULT, discover_layouts
        from veles.core.registry import ensure

        # Pre-bootstrap: no project exists yet, so discovery sees the
        # user-level and builtin packs (project-level packs can't exist
        # before init by definition); registry layouts come from the
        # cached clones (no network).
        installed = {p.manifest.name: p for p in discover_layouts(project=None)}
        names = ensure.available_layouts()
        if len(names) <= 1:
            ctx.answers["layout"] = names[0] if names else LAYOUT_DEFAULT
            return WizardOutcome.NEXT

        items = [
            ChoiceItem(
                label=f"{n} ({installed[n].scope})" if n in installed else f"{n} (registry)",
                value=n,
                description=(installed[n].manifest.description or "") if n in installed else "",
            )
            for n in names
        ]
        picked = await ctx.app.push_screen_wait(
            ChoiceScreen(
                title=self.title,
                items=items,
                subtitle=(
                    "Layouts shape how the agent stores user content. Default: bare. "
                    "More: `veles registry search --kind layout`."
                ),
                default=LAYOUT_DEFAULT,
            )
        )
        nav = outcome_from_dismiss(picked)
        if nav is not None:
            return nav
        layout = picked or LAYOUT_DEFAULT
        if layout not in installed:
            layout = _install_layout(ctx, layout)
        ctx.answers["layout"] = layout
        return WizardOutcome.NEXT


def _install_layout(ctx: WizardContext, name: str) -> str:
    """Install a registry layout picked in the wizard. The install's confirmation
    is a terminal prompt, so the app hands the terminal back while it runs."""
    from textual.app import SuspendNotSupported

    from veles.core.registry import ensure

    try:
        with ctx.app.suspend():
            return ensure.layout_or_default(name, interactive=True)
    except SuspendNotSupported:
        return ensure.layout_or_default(name, interactive=False)


__all__ = [
    "BootstrapStep",
    "DaemonModeStep",
    "LayoutPickerStep",
    "ProviderOverrideStep",
    "RecapStep",
    "project_wizard_steps",
]
