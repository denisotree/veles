"""Concrete steps for the project-level TUI wizard.

Run after the user wizard (or whenever cwd has no `.veles/project.toml`).
Bootstrap is the gate — declining cancels the whole flow. Subsequent
steps are independent and skippable.

Step order:
    1. Bootstrap            (confirm → init_project)
    2. Provider override    (optional; per-project API-key flow)
    3. AGENTS.md normalize  (only when CLAUDE.md/GEMINI.md conflicts exist;
                             stub here — full implementation lands in M96)
    4. Wiki seed            (only when there are seed candidates)
    5. Daemon mode          (optional; if accepted → host/port + Telegram
                             token + whitelist; else skipped)
    6. Recap                (always shown)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from shutil import copyfile

from veles.core.i18n import t
from veles.core.project import Project, ProjectAlreadyExists, init_project, load_project
from veles.core.wiki import Wiki
from veles.tui.wizard.screens import (
    ChoiceScreen,
    ConfirmScreen,
    InputScreen,
    MultiSelectScreen,
    ProgressScreen,
)
from veles.tui.wizard.screens.choice import ChoiceItem
from veles.tui.wizard.step import (
    CANCEL_SENTINEL as _CANCEL_SENTINEL,
    WizardContext,
    WizardOutcome,
    outcome_from_dismiss as _nav,
)

from veles.core.providers import ALL_PROVIDERS as _ALL_PROVIDERS

# Project picker keeps labels compact — the user has seen the tagline
# explanations in the first-run wizard already.
_PROVIDER_CHOICES = [
    ChoiceItem(label=spec.label, value=spec.value) for spec in _ALL_PROVIDERS
]


# ---------------- Step 1: Bootstrap ----------------


@dataclass
class BootstrapStep:
    """Confirm + run init_project. This step gates the whole wizard:
    declining returns CANCEL and the runner unwinds."""

    cwd: Path
    name: str = "bootstrap"
    title: str = "Initialize Veles project"

    async def run(self, ctx: WizardContext) -> WizardOutcome:
        # If the preceding user-wizard already asked "initialize here?" and
        # got a Yes, skip the duplicate confirm and go straight to init —
        # otherwise the user has to answer the same question twice (the
        # screen flashes for a moment, then re-appears identical).
        if ctx.answers.get("_skip_bootstrap_confirm"):
            try:
                project = init_project(self.cwd, name=None, force=False)
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
        nav = _nav(result)
        if nav is not None:
            return nav
        if not result:
            return WizardOutcome.CANCEL
        try:
            project = init_project(self.cwd, name=None, force=False)
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
        nav = _nav(wants)
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
                items=_PROVIDER_CHOICES,
                subtitle=t("project_wizard.ask_provider_label"),
                default=default_provider,
            )
        )
        nav = _nav(picked)
        if nav is not None:
            return nav

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
        cfg.setdefault("provider", {})
        cfg["provider"]["default"] = picked
        if picked_model:
            cfg["provider"]["model"] = picked_model
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
    from veles.core.provider_factory import LOCAL_PROVIDERS
    from veles.core.secrets import get_provider_key
    from veles.tui.screens._model_fetcher import (
        known_models,
        validate_and_fetch_models,
    )

    project: Project = ctx.answers["project"]
    slug = project.name
    if provider in LOCAL_PROVIDERS:
        api_key = "local"
    else:
        api_key = get_provider_key(provider, project=slug) or ""
        if not api_key:
            return None

    ok, models, _err = validate_and_fetch_models(provider, api_key)
    if not ok or not models:
        models = list(known_models(provider))
    if not models:
        return None
    models = sorted(models, key=str.casefold)
    items = [ChoiceItem(label=m, value=m) for m in models]
    default = default_pref if default_pref in models else models[0]
    result = await ctx.app.push_screen_wait(
        ChoiceScreen(
            title="Project model override",
            items=items,
            subtitle=f"{len(models)} model(s) available from {provider}.",
            default=default,
            filterable=True,
            filter_placeholder="filter models (e.g. claude, gpt, 70b)",
        )
    )
    if result is None or result == _CANCEL_SENTINEL:
        return None
    return str(result)


async def _project_api_key_flow(
    ctx: WizardContext, project: Project, provider: str
) -> None:
    """Same shape as user-level ApiKeyStep but writes to the project scope."""
    from veles.core.provider_factory import LOCAL_PROVIDERS, PROVIDER_API_KEY_ENVS
    from veles.core.secrets import (
        KeyringUnavailable,
        get_provider_key,
        set_provider_key,
    )

    if provider in LOCAL_PROVIDERS or provider in ("claude-cli", "gemini-cli"):
        ctx.answers["project_api_key_status"] = "not-required"
        return

    slug = project.name
    default_key = get_provider_key(provider, env_fallback=False)
    env_value: str | None = None
    env_name: str | None = None
    for name in PROVIDER_API_KEY_ENVS.get(provider, ()):
        value = os.environ.get(name)
        if value:
            env_value, env_name = value, name
            break

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
    if choice is None or choice == _CANCEL_SENTINEL or choice == "skip":
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


# ---------------- Step 3: AGENTS.md normalization (M96 stub) ----------------


@dataclass
class NormalizationStep:
    """Detects AGENTS.md / CLAUDE.md / GEMINI.md conflicts. Full LLM-merge
    lands in M96; for now we record what we'd merge so the recap screen
    can mention it and the user knows to expect the prompt later."""

    name: str = "agents_md_normalization"
    title: str = "AGENTS.md normalization"

    async def run(self, ctx: WizardContext) -> WizardOutcome:
        project: Project = ctx.answers["project"]
        conflicts = _detect_context_file_conflicts(project.root)
        if not conflicts:
            ctx.answers["normalization"] = "no-conflict"
            return WizardOutcome.SKIP
        sample = ", ".join(conflicts)
        wants = await ctx.app.push_screen_wait(
            ConfirmScreen(
                title=self.title,
                question=(
                    f"Found context files outside Veles convention: {sample}. "
                    "Merge them into a single AGENTS.md? Smart merge of "
                    "multiple context files is coming soon; for now we'll "
                    "just record the intent and continue."
                ),
                default=False,
            )
        )
        nav = _nav(wants)
        if nav is not None:
            return nav
        ctx.answers["normalization"] = {
            "files": conflicts,
            "wants_merge": bool(wants),
        }
        return WizardOutcome.NEXT


def _detect_context_file_conflicts(root: Path) -> list[str]:
    """Return the list of files (relative names) that are real files and
    not symlinks pointing at AGENTS.md."""
    names = ("AGENTS.md", "CLAUDE.md", "GEMINI.md")
    real_files: list[str] = []
    for name in names:
        p = root / name
        try:
            if p.exists() and not p.is_symlink():
                real_files.append(name)
        except OSError:
            continue
    return real_files if len(real_files) >= 2 else []


# ---------------- Step 4: Wiki seed ----------------


@dataclass
class WikiSeedStep:
    cwd: Path
    name: str = "wiki_seed"
    title: str = "Seed wiki/sources/"

    async def run(self, ctx: WizardContext) -> WizardOutcome:
        candidates = _collect_seed_candidates(self.cwd)
        if not candidates:
            ctx.answers["wiki_seed_count"] = 0
            return WizardOutcome.SKIP
        sample = ", ".join(str(p.relative_to(self.cwd)) for p in candidates[:3])
        extra = f" (+ {len(candidates) - 3} more)" if len(candidates) > 3 else ""
        wants = await ctx.app.push_screen_wait(
            ConfirmScreen(
                title=self.title,
                question=t("project_wizard.ask_wiki_seed", sample=sample, extra=extra),
                default=False,
            )
        )
        nav = _nav(wants)
        if nav is not None:
            return nav
        if not wants:
            ctx.answers["wiki_seed_count"] = 0
            return WizardOutcome.SKIP
        project: Project = ctx.answers["project"]
        seeded = _copy_seed_files(project, candidates)
        ctx.answers["wiki_seed_count"] = seeded
        return WizardOutcome.NEXT


# ---------------- Step 5: Daemon mode + Telegram ----------------


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
                    "remote sessions, and Telegram-channel integration."
                ),
                default=False,
            )
        )
        nav = _nav(wants)
        if nav is not None:
            return nav
        if not wants:
            ctx.answers["daemon"] = None
            return WizardOutcome.SKIP

        host = await ctx.app.push_screen_wait(
            InputScreen(
                title=self.title,
                prompt="Daemon host (Enter for 127.0.0.1)",
                default="127.0.0.1",
            )
        )
        nav = _nav(host)
        if nav is not None:
            return nav
        port = await ctx.app.push_screen_wait(
            InputScreen(
                title=self.title,
                prompt="Daemon port (Enter for 8765)",
                default="8765",
            )
        )
        nav = _nav(port)
        if nav is not None:
            return nav
        host_clean = host.strip() or "127.0.0.1"
        port_clean = int(port.strip() or "8765")
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
        await _telegram_subflow(ctx)
        return WizardOutcome.NEXT


async def _telegram_subflow(ctx: WizardContext) -> None:
    wants = await ctx.app.push_screen_wait(
        ConfirmScreen(
            title="Telegram channel",
            question=t("project_wizard.ask_telegram"),
            default=False,
        )
    )
    if not wants or wants == _CANCEL_SENTINEL:
        ctx.answers["telegram"] = None
        return
    token_input = await ctx.app.push_screen_wait(
        InputScreen(
            title="Telegram channel",
            prompt=t("project_wizard.ask_telegram_token"),
            password=True,
        )
    )
    if token_input is None or token_input == _CANCEL_SENTINEL or not token_input.strip():
        ctx.answers["telegram"] = None
        return
    whitelist = await ctx.app.push_screen_wait(
        MultiSelectScreen(
            title="Telegram whitelist",
            items=[],  # populate from prior projects later (M97+)
            allow_freeform=True,
            freeform_placeholder="@username or numeric user id, comma-separated",
        )
    )
    if whitelist is None or _CANCEL_SENTINEL in (whitelist or []):
        whitelist = []
    project: Project = ctx.answers["project"]
    # Token goes to the keychain; chat_id / whitelist stay in project config.
    from veles.core.secrets import KeyringUnavailable, set_provider_key

    try:
        set_provider_key("telegram", token_input.strip(), project=project.name)
        token_status = "saved-keychain"
    except KeyringUnavailable as exc:
        token_status = f"keychain-unavailable: {exc}"
    cfg = _load_project_toml(project)
    cfg.setdefault("channels", {}).setdefault("telegram", {})
    cfg["channels"]["telegram"]["enabled"] = True
    cfg["channels"]["telegram"]["whitelist"] = list(whitelist or [])
    _save_project_toml(project, cfg)
    ctx.answers["telegram"] = {
        "whitelist": list(whitelist or []),
        "token_status": token_status,
    }


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
            lines.append(f"  · provider override: {ov['provider']}/{ov['model'] or '<inherit-model>'}")
        if ctx.answers.get("wiki_seed_count"):
            lines.append(f"  · seeded {ctx.answers['wiki_seed_count']} file(s) into wiki/sources/")
        d = ctx.answers.get("daemon")
        if d:
            lines.append(f"  · daemon: {d['host']}:{d['port']}")
        if ctx.answers.get("telegram"):
            wl = ctx.answers["telegram"]["whitelist"]
            lines.append(f"  · telegram: {len(wl)} user(s) whitelisted")
        try:
            pages = Wiki(project.wiki_root).reindex_if_stale()
        except Exception:
            pages = 0
        if pages:
            lines.append(f"  · indexed {pages} wiki page(s)")
        await ctx.app.push_screen_wait(
            ProgressScreen(title=self.title, lines=lines)
        )
        return WizardOutcome.NEXT


# ---------------- helpers (re-used from cli/project_wizard.py) ----------------


def _collect_seed_candidates(cwd: Path, *, cap: int = 25) -> list[Path]:
    seen: list[Path] = []
    readme = cwd / "README.md"
    if readme.is_file():
        seen.append(readme)
    try:
        for entry in sorted(cwd.glob("*.md")):
            if entry.is_file() and entry not in seen:
                seen.append(entry)
    except OSError:
        pass
    docs = cwd / "docs"
    if docs.is_dir():
        try:
            for entry in sorted(docs.rglob("*.md")):
                if entry.is_file() and entry not in seen:
                    seen.append(entry)
        except OSError:
            pass
    return seen[:cap]


def _copy_seed_files(project: Project, candidates: list[Path]) -> int:
    Wiki(project.wiki_root).ensure_layout()
    target_root = project.wiki_root / "sources" / "seed"
    target_root.mkdir(parents=True, exist_ok=True)
    count = 0
    for src in candidates:
        try:
            rel = src.relative_to(project.root)
        except ValueError:
            rel = Path(src.name)
        dst = target_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            copyfile(src, dst)
            count += 1
        except OSError:
            continue
    return count


# Thin aliases — historic name kept for in-file call sites; the real
# loader/saver lives in `core.project_config` (M-R1.2).
from veles.core.project_config import (
    load_project_config as _load_project_toml,
    save_project_config as _save_project_toml,
)


def project_wizard_steps(cwd: Path) -> list:
    return [
        BootstrapStep(cwd=cwd),
        LayoutPickerStep(),
        ProviderOverrideStep(),
        NormalizationStep(),
        WikiSeedStep(cwd=cwd),
        DaemonModeStep(),
        RecapStep(),
    ]


# ---------------- M117e: LayoutPickerStep ----------------


@dataclass
class LayoutPickerStep:
    """Pick the project's content layout-pack (default `llm-wiki`).

    Runs right after BootstrapStep so the project skeleton already
    exists — we just rewrite its `layout` field. Single-pack
    installations (only the builtin `llm-wiki`) auto-confirm without
    showing the screen; the picker appears only when the user has
    actually installed alternative packs into `~/.veles/layouts/`
    or `<project>/.veles/layouts/`.
    """

    name: str = "layout-picker"
    title: str = "Pick a content layout"

    async def run(self, ctx: WizardContext) -> WizardOutcome:
        project: Project | None = ctx.answers.get("project")
        if project is None:
            return WizardOutcome.NEXT

        from veles.core.layout import LAYOUT_DEFAULT, discover_layouts

        packs = discover_layouts(project=project)
        if len(packs) <= 1:
            # Only the builtin pack — no choice to offer. Keep the
            # default that init_project already wrote.
            ctx.answers["layout"] = project.layout_name
            return WizardOutcome.NEXT

        items = [
            ChoiceItem(
                label=f"{pack.manifest.name} ({pack.scope})",
                value=pack.manifest.name,
                description=pack.manifest.description or "",
            )
            for pack in packs
        ]
        picked = await ctx.app.push_screen_wait(
            ChoiceScreen(
                title=self.title,
                items=items,
                subtitle="Layouts shape how the agent stores user content. Default: llm-wiki.",
                default=project.layout_name or LAYOUT_DEFAULT,
            )
        )
        nav = _nav(picked)
        if nav is not None:
            return nav
        if picked is None or picked == project.layout_name:
            ctx.answers["layout"] = project.layout_name
            return WizardOutcome.NEXT

        # Rewrite project.toml with the new layout selection. We
        # re-emit the whole file via _write_project_toml so
        # subsequent migrations still see a clean shape.
        from veles.core.project import _write_project_toml

        _write_project_toml(
            project.project_toml_path,
            name=project.name,
            created_at=project.created_at,
            schema_version=project.schema_version,
            layout_name=picked,
        )
        # Mutate the in-memory dataclass too so later steps see the
        # new value without a reload.
        project.layout_name = picked
        ctx.answers["layout"] = picked
        return WizardOutcome.NEXT


__all__ = [
    "BootstrapStep",
    "DaemonModeStep",
    "LayoutPickerStep",
    "NormalizationStep",
    "ProviderOverrideStep",
    "RecapStep",
    "WikiSeedStep",
    "project_wizard_steps",
]
