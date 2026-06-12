"""Concrete steps for the user-level (first-run) TUI wizard.

Each step pushes one or two modal screens, then records the answer (or
side-effect like saving a keychain entry) into `ctx.answers`. Returns
NEXT / BACK / SKIP / CANCEL per the runner protocol.

The order — Language → Provider → API key → Theme → Initialize project
here? — is dictated by data flow: provider must be picked before we know
which API key env var to consult, theme is independent (any moment),
"initialize project" runs last and hands control to the project wizard.
"""

from __future__ import annotations

import contextlib
import os
from dataclasses import dataclass

from veles.core.providers import ALL_PROVIDERS as _ALL_PROVIDERS
from veles.core.providers import tui_label
from veles.tui.wizard.screens import (
    ChoiceScreen,
    ConfirmScreen,
    InputScreen,
)
from veles.tui.wizard.screens.choice import ChoiceItem
from veles.tui.wizard.step import (
    CANCEL_SENTINEL as _CANCEL_SENTINEL,
)
from veles.tui.wizard.step import WizardContext, WizardOutcome
from veles.tui.wizard.step import (
    outcome_from_dismiss as _outcome_from_dismiss,
)

# Language choices ship with the i18n module (M91); these labels are
# canonical and don't need translation themselves.
_LANGUAGES = [
    ChoiceItem(label="English", value="en"),
    ChoiceItem(label="Русский", value="ru"),
]

_PROVIDERS = [ChoiceItem(label=tui_label(spec), value=spec.value) for spec in _ALL_PROVIDERS]


# ---------------- Step 1: Language ----------------


@dataclass
class LanguageStep:
    name: str = "language"
    title: str = "Step 1/6 — Language"

    async def run(self, ctx: WizardContext) -> WizardOutcome:
        result = await ctx.app.push_screen_wait(
            ChoiceScreen(
                title=self.title,
                items=_LANGUAGES,
                subtitle="Choose your interface language.",
                default=ctx.answers.get("language", "en"),
            )
        )
        nav = _outcome_from_dismiss(result)
        if nav is not None:
            return nav
        ctx.answers["language"] = result
        return WizardOutcome.NEXT


# ---------------- Step 2: Default provider ----------------


@dataclass
class ProviderStep:
    name: str = "provider"
    title: str = "Step 2/6 — Default LLM provider"

    async def run(self, ctx: WizardContext) -> WizardOutcome:
        result = await ctx.app.push_screen_wait(
            ChoiceScreen(
                title=self.title,
                items=_PROVIDERS,
                subtitle=("Veles can talk to any of these. You can override per-project later."),
                default=ctx.answers.get("default_provider", "openrouter"),
            )
        )
        nav = _outcome_from_dismiss(result)
        if nav is not None:
            return nav
        ctx.answers["default_provider"] = result
        return WizardOutcome.NEXT


# ---------------- Step 3: API key flow ----------------


@dataclass
class ApiKeyStep:
    """Branch based on what's already known about the chosen provider:
    - CLI / local providers → SKIP (no key needed).
    - Keychain has a default-scope entry → ask use vs replace.
    - ENV var present → ask use ENV vs save to keychain vs enter new.
    - Nothing known → prompt for the key, save to keychain.
    """

    name: str = "api_key"
    title: str = "Step 3/6 — API key"

    async def run(self, ctx: WizardContext) -> WizardOutcome:
        from veles.core.provider_factory import LOCAL_PROVIDERS, PROVIDER_API_KEY_ENVS
        from veles.core.secrets import (
            KeyringUnavailable,
            get_provider_key,
            set_provider_key,
        )

        provider = ctx.answers["default_provider"]
        if provider in LOCAL_PROVIDERS or provider in ("claude-cli", "gemini-cli"):
            ctx.answers["api_key_status"] = "not-required"
            return WizardOutcome.SKIP

        env_names = PROVIDER_API_KEY_ENVS.get(provider, ())
        keychain_key = get_provider_key(provider, env_fallback=False)
        env_value, env_name = None, None
        for name in env_names:
            value = os.environ.get(name)
            if value:
                env_value, env_name = value, name
                break

        if keychain_key:
            choice = await ctx.app.push_screen_wait(
                ChoiceScreen(
                    title=self.title,
                    subtitle=f"Found {provider} key in the OS keychain.",
                    items=[
                        ChoiceItem("Use existing key", "use"),
                        ChoiceItem("Replace with a new key", "replace"),
                    ],
                    default="use",
                )
            )
            nav = _outcome_from_dismiss(choice)
            if nav is not None:
                return nav
            if choice == "use":
                ctx.answers["api_key_status"] = "kept-keychain"
                return WizardOutcome.NEXT
            # else fall through to input
        elif env_value:
            choice = await ctx.app.push_screen_wait(
                ChoiceScreen(
                    title=self.title,
                    subtitle=f"Found {env_name} in the environment.",
                    items=[
                        ChoiceItem("Use the ENV value (re-read each run)", "env"),
                        ChoiceItem("Save the ENV value to the keychain", "save_env"),
                        ChoiceItem("Enter a different key", "input"),
                    ],
                    default="env",
                )
            )
            nav = _outcome_from_dismiss(choice)
            if nav is not None:
                return nav
            if choice == "env":
                ctx.answers["api_key_status"] = "env"
                return WizardOutcome.NEXT
            if choice == "save_env":
                try:
                    set_provider_key(provider, env_value)
                    ctx.answers["api_key_status"] = "saved-from-env"
                except KeyringUnavailable as exc:
                    ctx.answers["api_key_status"] = f"keychain-unavailable: {exc}"
                return WizardOutcome.NEXT
            # else fall through to input

        entered = await ctx.app.push_screen_wait(
            InputScreen(
                title=self.title,
                prompt=f"Paste your {provider} API key. Stored in the OS keychain.",
                password=True,
            )
        )
        nav = _outcome_from_dismiss(entered)
        if nav is not None:
            return nav
        if not entered.strip():
            # Empty input — treat as SKIP so user can configure later.
            ctx.answers["api_key_status"] = "deferred"
            return WizardOutcome.SKIP
        try:
            set_provider_key(provider, entered.strip())
            ctx.answers["api_key_status"] = "saved-new"
        except KeyringUnavailable as exc:
            ctx.answers["api_key_status"] = f"keychain-unavailable: {exc}"
        return WizardOutcome.NEXT


# ---------------- Step 4: Default model (fetched from provider) ----------------


@dataclass
class ModelStep:
    """Show the list of models actually available for the chosen provider
    and let the user pick a default.

    Uses `validate_and_fetch_models(provider, key)` which doubles as an
    API-key sanity check — if the provider rejects the key, the user
    gets a chance to fix it (BACK) or skip with the fallback default.

    Skipped (no answer written) for:
      - providers without a key (local / cli shims) where `validate`
        returns curated → we still show the picker with curated options.
      - providers where the user deferred the key entirely.
    """

    name: str = "default_model"
    title: str = "Step 4/6 — Default model"

    async def run(self, ctx: WizardContext) -> WizardOutcome:
        from veles.core.provider_factory import LOCAL_PROVIDERS
        from veles.core.secrets import get_provider_key
        from veles.tui.screens._model_fetcher import (
            known_models,
            validate_and_fetch_models,
        )

        provider = ctx.answers["default_provider"]
        api_status = ctx.answers.get("api_key_status", "")
        # Resolve the key the user just configured; for local providers
        # this is a sentinel ("local") because the adapter doesn't
        # authenticate but still serves /models.
        if provider in LOCAL_PROVIDERS:
            api_key = "local"
        elif api_status == "deferred":
            # No key configured — fall back to curated list so the picker
            # still shows the canonical names.
            ctx.answers["default_model"] = None
            return WizardOutcome.SKIP
        else:
            api_key = get_provider_key(provider) or ""
            if not api_key:
                ctx.answers["default_model"] = None
                return WizardOutcome.SKIP

        ok, models, error = validate_and_fetch_models(provider, api_key)
        if not ok:
            # Confirm + bounce: go BACK to ApiKeyStep so the user can
            # paste a correct key.
            retry = await ctx.app.push_screen_wait(
                ConfirmScreen(
                    title=self.title,
                    question=(
                        f"The {provider} API rejected the key (reason: {error}). "
                        "Go back to re-enter the key?"
                    ),
                    default=True,
                )
            )
            if retry is True:
                return WizardOutcome.BACK
            if retry == _CANCEL_SENTINEL:
                return WizardOutcome.CANCEL
            # `No` — accept the key as-is, leave default_model unset.
            ctx.answers["default_model"] = None
            ctx.answers["api_key_status"] = "deferred"
            return WizardOutcome.SKIP

        if not models:
            models = list(known_models(provider))
        # Sort alphabetically (case-insensitive) so the picker is browsable
        # without scanning. The filter input below makes long provider
        # lists (OpenRouter ships ~300 entries) usable.
        models = sorted(models, key=str.casefold)
        items = [ChoiceItem(label=m, value=m) for m in models]
        default = ctx.answers.get("default_model") or models[0]
        result = await ctx.app.push_screen_wait(
            ChoiceScreen(
                title=self.title,
                items=items,
                subtitle=f"{len(models)} model(s) available from {provider}.",
                default=default,
                filterable=True,
                filter_placeholder="filter models (e.g. claude, gpt, 70b)",
            )
        )
        nav = _outcome_from_dismiss(result)
        if nav is not None:
            return nav
        ctx.answers["default_model"] = result
        return WizardOutcome.NEXT


# ---------------- Step 5: Theme ----------------


@dataclass
class ThemeStep:
    name: str = "theme"
    title: str = "Step 5/6 — TUI theme"

    async def run(self, ctx: WizardContext) -> WizardOutcome:
        from veles.cli.tui_theme import THEMES
        from veles.tui.theme_bridge import apply_to_app

        items = [ChoiceItem(label=name, value=name) for name in sorted(THEMES.keys())]
        default = ctx.answers.get("tui_theme", "everforest")
        # Snapshot the current theme so we can roll back on BACK/CANCEL —
        # the wizard's live preview otherwise leaves the user on a
        # half-chosen theme they may not have wanted.
        snapshot = ctx.app.theme

        def _preview(theme_name: str) -> None:
            apply_to_app(ctx.app, theme_name)

        result = await ctx.app.push_screen_wait(
            ChoiceScreen(
                title=self.title,
                items=items,
                subtitle="You can change this later via Ctrl+T. Preview is live as you navigate.",
                default=default,
                on_highlight_changed=_preview,
            )
        )
        nav = _outcome_from_dismiss(result)
        if nav is not None:
            # Roll back to whatever was active before this step.
            with contextlib.suppress(Exception):
                ctx.app.theme = snapshot
            return nav
        ctx.answers["tui_theme"] = result
        apply_to_app(ctx.app, result)
        return WizardOutcome.NEXT


# ---------------- Step 5: Initialize project here? ----------------


@dataclass
class InitProjectStep:
    """If the user agrees, the project wizard runs inline right after
    the user wizard returns. Just records the answer here."""

    name: str = "init_project"
    title: str = "Step 6/6 — Initialize this directory?"

    async def run(self, ctx: WizardContext) -> WizardOutcome:
        from pathlib import Path

        cwd = Path.cwd()
        result = await ctx.app.push_screen_wait(
            ConfirmScreen(
                title=self.title,
                question=(
                    f"Initialize {cwd} as a Veles project? "
                    "Creates `.veles/` and an AGENTS.md template. "
                    "You can answer No and run `veles init` later."
                ),
                default=True,
            )
        )
        if result == _CANCEL_SENTINEL:
            return WizardOutcome.CANCEL
        if result is None:
            return WizardOutcome.BACK
        ctx.answers["init_project_here"] = bool(result)
        return WizardOutcome.NEXT


def user_wizard_steps() -> list:
    return [
        LanguageStep(),
        ProviderStep(),
        ApiKeyStep(),
        ModelStep(),
        ThemeStep(),
        InitProjectStep(),
    ]


__all__ = [
    "ApiKeyStep",
    "InitProjectStep",
    "LanguageStep",
    "ModelStep",
    "ProviderStep",
    "ThemeStep",
    "user_wizard_steps",
]
