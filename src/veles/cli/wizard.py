"""First-run interactive wizard (M47) — VISION §7 onboarding.

Triggers from `cli/__init__.py::main` when ALL of:
- `~/.veles/config.toml` is missing.
- stdin is a TTY.
- `--no-wizard` was not passed.
- `VELES_NO_WIZARD=1` is not set in the env.
- The active command isn't a bootstrap one (`init`, `import`) — those
  set up state themselves and the wizard would interleave awkwardly.

Asks three things and writes `~/.veles/config.toml`:
1. Preferred language (`en` / `ru`) — recorded for future UI strings.
2. Default LLM provider — bare-list choice from `_PROVIDER_CHOICES`.
3. (Soft hint only) which API-key env var to set; **NEVER persists keys**.

Optional first-project name field exists in the schema but the wizard
itself doesn't run `veles init` — that's a separate explicit user action.

Tests inject a fake prompter via `set_wizard_prompter` (ContextVar
override). The default prompter is stdin-backed; non-TTY contexts
short-circuit before reaching it via the gate above.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable
from contextvars import ContextVar, Token
from dataclasses import dataclass

from veles.core.provider_factory import PROVIDER_API_KEY_ENVS
from veles.core.providers import PROVIDER_VALUES as _PROVIDER_CHOICES
from veles.core.user_config import (
    UserConfig,
    load_user_config,
    save_user_config,
    user_config_path,
)

_LANGUAGES: tuple[str, ...] = ("en", "ru")
_BOOTSTRAP_COMMANDS: frozenset[str] = frozenset({"init", "import"})


Prompter = Callable[[str, str | None], str]
"""Wizard input function: (prompt_label, default_value) -> raw_answer."""


@dataclass(frozen=True, slots=True)
class WizardResult:
    config: UserConfig
    saved_to: object  # pathlib.Path; left as Object to avoid forced import order


_wizard_prompter: ContextVar[Prompter | None] = ContextVar("veles_wizard_prompter", default=None)


def set_wizard_prompter(p: Prompter | None) -> Token:
    return _wizard_prompter.set(p)


def reset_wizard_prompter(token: Token) -> None:
    _wizard_prompter.reset(token)


def should_run_wizard(args: argparse.Namespace) -> bool:
    """Decide whether to fire the wizard before dispatching `args.command`."""
    if getattr(args, "no_wizard", False):
        return False
    if os.environ.get("VELES_NO_WIZARD") == "1":
        return False
    if getattr(args, "command", None) in _BOOTSTRAP_COMMANDS:
        return False
    if not sys.stdin.isatty():
        return False
    return not user_config_path().is_file()


def run_wizard() -> WizardResult:
    """Interactive flow. Caller is responsible for the gate (`should_run_wizard`).

    Persists the answers to `~/.veles/config.toml` and returns the
    saved config. Subsequent CLI invocations short-circuit because
    `should_run_wizard()` returns False once the file exists.
    """
    prompter = _wizard_prompter.get() or _default_prompter
    print(
        "\nWelcome to Veles. A one-time setup will write ~/.veles/config.toml.\n",
        file=sys.stderr,
    )
    language = _ask_choice(prompter, "Preferred language", _LANGUAGES, default="en")
    provider = _ask_choice(
        prompter,
        "Default LLM provider",
        _PROVIDER_CHOICES,
        default="openrouter",
    )
    _hint_about_api_key(provider)
    first_project = prompter("First project name (optional, blank to skip)", None).strip() or None

    cfg = UserConfig(
        language=language,
        default_provider=provider,
        first_project_name=first_project,
    )
    target = user_config_path()
    save_user_config(cfg, target)
    print(f"\n<wrote {target}>", file=sys.stderr)
    return WizardResult(config=cfg, saved_to=target)


def _ask_choice(prompter: Prompter, prompt: str, choices: tuple[str, ...], *, default: str) -> str:
    """Ask until the user picks one of `choices` (or accepts the default)."""
    while True:
        ans = (
            prompter(
                f"{prompt} [{'/'.join(choices)}]",
                default,
            )
            .strip()
            .lower()
        )
        if not ans:
            return default
        if ans in choices:
            return ans
        print(
            f"  ! '{ans}' is not one of {choices}; try again.",
            file=sys.stderr,
        )


def _hint_about_api_key(provider: str) -> None:
    envs = PROVIDER_API_KEY_ENVS.get(provider)
    if not envs:
        # cli-delegate providers authenticate via their own binary.
        return
    if any(os.environ.get(name) for name in envs):
        return
    label = " or ".join(envs)
    print(
        f"  tip: set {label} in your shell profile so Veles can talk to {provider}.",
        file=sys.stderr,
    )


def _default_prompter(prompt: str, default: str | None) -> str:
    """Stdin-backed prompter. Returns `default` (or '') on EOF / non-TTY."""
    if not sys.stdin.isatty():
        return default or ""
    label = f"  {prompt}"
    if default is not None:
        label = f"{label} [default: {default}]"
    try:
        return input(f"{label}: ")
    except EOFError:
        return default or ""


def maybe_run_first_run_wizard(args: argparse.Namespace) -> None:
    """Run the wizard if the gate allows, swallowing all I/O errors.

    Called from `cli/__init__.py::main` before dispatching the verb.
    Prefers the M94 Textual flow (`tui/wizard/user_runner`) when stdin
    is a TTY; falls back to the legacy stdin flow on any failure or on
    headless invocations. Best-effort: failure is reported to stderr but
    never blocks the user's actual command — the next launch will retry.

    The user wizard's optional final step asks "initialize project here?"
    On `No` we set `args.no_wizard = True` so the dispatcher's downstream
    project-wizard hook stays quiet.
    """
    if not should_run_wizard(args):
        return
    try:
        # TUI wizard requires a real terminal on both sides. Pytest captures
        # stdout (isatty=False) so test runs fall through to the stdin path.
        tui_eligible = sys.stdin.isatty() and sys.stdout.isatty()
        try:
            if not tui_eligible:
                raise ImportError("TUI not eligible in non-interactive shell")
            from veles.tui.wizard.user_runner import run_user_wizard_tui

            cfg, raw = run_user_wizard_tui()
            if cfg is None:
                print(
                    "\n<wizard cancelled; will retry next launch>",
                    file=sys.stderr,
                )
                args._wizard_user_chose_no_project = True
                return
            # Respect "No" on the final init-project question by
            # suppressing the project-wizard hook downstream AND telling
            # main() that the user made a conscious choice — main() then
            # exits 0 instead of printing the generic "no project" error.
            if raw.get("init_project_here") is False:
                args.no_wizard = True
                args._wizard_user_chose_no_project = True
            elif raw.get("init_project_here") is True:
                # Carry the answer into the project-wizard so its
                # BootstrapStep skips the duplicate Initialize? confirm.
                args._wizard_init_project_here = True
            return
        except ImportError:
            # Textual not available (degraded environment). Fall back.
            pass
        except Exception as exc:
            print(
                f"warning: TUI wizard failed ({type(exc).__name__}: {exc}); "
                "falling back to stdin prompts.",
                file=sys.stderr,
            )
        run_wizard()
    except KeyboardInterrupt:
        print("\n<wizard interrupted; will retry next launch>", file=sys.stderr)
    except Exception as exc:
        print(
            f"warning: first-run wizard failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )


def existing_user_config() -> UserConfig | None:
    """Convenience accessor for callers that want the saved config."""
    return load_user_config()
