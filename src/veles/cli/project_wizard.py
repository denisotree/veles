"""M82: project-level wizard.

Triggered when an agent-flow command (`run`, `tui`, `add`, `ingest`,
`query`, ...) finds no `.veles/` in cwd or any parent. Mirrors the
user-level wizard's shape: pre-Textual stdin prompts, ContextVar-backed
prompter for tests, every step opt-in with skip-by-default.

Steps (each gated by its own y/N, default `n` = skip):
  1. Bootstrap — confirm + run `init_project(cwd)`. This step is the
     wizard's gate; declining returns None and the caller exits with
     the standard "no project found" error.
  2. Provider override — optional `.veles/config.toml` `[provider]` block.
     Default = inherit from user-level config.
  3. Wiki seed from existing docs — copy `README.md`, `*.md` in `docs/`,
     and top-level `*.md` files into `wiki/sources/`. Pure file copy;
     no LLM ingest at wizard time (offline-friendly, no API key needed).
  4. Telegram channel — optional bot token + chat_id, written to
     `.veles/config.toml`. No online validation.

The wizard creates `.veles/` early (step 1), so a partial completion
(Ctrl+C between steps) is idempotent — the directory check below stops
the wizard from re-firing on the next invocation.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import sys
from collections.abc import Callable
from contextvars import ContextVar, Token
from pathlib import Path
from shutil import copyfile

from veles.core.i18n import t
from veles.core.project import Project, ProjectAlreadyExists, init_project
from veles.core.project_config import (
    load_project_config as _load_project_toml,
)
from veles.core.project_config import (
    save_project_config as _save_project_toml,
)
from veles.core.providers import PROVIDER_VALUES as _PROVIDER_CHOICES
from veles.core.wiki import Wiki

Prompter = Callable[[str, str | None], str]
"""(prompt_label, default_value) -> raw_answer."""


def _project_config_path(project: Project) -> Path:
    """User-overridable project config (provider, channels, etc.).
    Distinct from `project.toml` which holds auto-managed metadata
    (name, created_at). Mirrors `~/.veles/config.toml` shape."""
    return project.state_dir / "config.toml"


# Commands that already own project scaffolding or are pure-global; the
# wizard must not fire for them even if no project exists.
_SKIP_COMMANDS: frozenset[str] = frozenset({"init", "import", "models", "doctor", "schema"})

_project_wizard_prompter: ContextVar[Prompter | None] = ContextVar(
    "veles_project_wizard_prompter", default=None
)


def set_project_wizard_prompter(p: Prompter | None) -> Token:
    return _project_wizard_prompter.set(p)


def reset_project_wizard_prompter(token: Token) -> None:
    _project_wizard_prompter.reset(token)


def should_run_project_wizard(args: argparse.Namespace, cwd: Path) -> bool:
    """Gate for the project wizard. Returns True iff every condition holds:
    no project ancestor here or above, TTY, not opted out, not a bootstrap
    verb. Project ancestor is determined by the same marker
    `core/project.py` uses (`.veles/project.toml`), so a bare `~/.veles/`
    user-config directory never satisfies the check."""
    if getattr(args, "no_wizard", False):
        return False
    if os.environ.get("VELES_NO_WIZARD") == "1":
        return False
    if getattr(args, "command", None) in _SKIP_COMMANDS:
        return False
    if not sys.stdin.isatty():
        return False
    from veles.core.project import find_project_root

    return find_project_root(cwd) is None


def run_project_wizard(cwd: Path) -> Project | None:
    """Interactive flow. Returns the new Project on bootstrap, or None
    if the user declined step 1."""
    prompter = _project_wizard_prompter.get() or _default_prompter
    print("\n" + t("project_wizard.intro_no_project", cwd=cwd) + "\n", file=sys.stderr)
    if not _ask_yes_no(prompter, t("project_wizard.ask_initialize"), default=True):
        return None

    try:
        project = init_project(cwd, name=None, force=False)
    except ProjectAlreadyExists:
        # Race: someone created `.veles/` since the gate; load and continue.
        from veles.core.project import load_project

        project = load_project(cwd)
    print(t("project_wizard.created_state", state_dir=project.state_dir), file=sys.stderr)

    from veles.core.layout.engines import wiki_enabled

    _step_provider_override(project, prompter)
    if wiki_enabled(project):
        _step_wiki_seed(project, prompter, cwd)
    _step_telegram(project, prompter)

    # Seed the FTS index so the post-init promise — "files will be
    # indexed" — actually holds. Cheap (empty / few-page) wiki rebuild.
    # M162: only when the layout pack activates the wiki engine.
    pages = 0
    if wiki_enabled(project):
        try:
            pages = Wiki(project.wiki_root).reindex_if_stale()
        except Exception:
            pages = 0
    if pages:
        print(t("project_wizard.indexed_wiki", pages=pages), file=sys.stderr)

    print("\n" + t("project_wizard.ready", name=project.name) + "\n", file=sys.stderr)
    return project


# ---------------- steps ----------------


def _step_provider_override(project: Project, prompter: Prompter) -> None:
    if not _ask_yes_no(prompter, t("project_wizard.ask_provider_override"), default=False):
        return
    provider = _ask_choice(
        prompter, t("project_wizard.ask_provider_label"), _PROVIDER_CHOICES, default="openrouter"
    )
    model = prompter(t("project_wizard.ask_model_label"), None).strip() or None
    cfg = _load_project_toml(project)
    cfg.setdefault("provider", {})
    cfg["provider"]["default"] = provider
    if model:
        cfg["provider"]["model"] = model
    _save_project_toml(project, cfg)
    print(
        t("project_wizard.provider_written", path=_project_config_path(project)),
        file=sys.stderr,
    )


def _step_wiki_seed(project: Project, prompter: Prompter, cwd: Path) -> None:
    candidates = _collect_seed_candidates(cwd)
    if not candidates:
        return
    sample = ", ".join(str(p.relative_to(cwd)) for p in candidates[:3])
    extra = f" (+ {len(candidates) - 3} more)" if len(candidates) > 3 else ""
    if not _ask_yes_no(
        prompter,
        t("project_wizard.ask_wiki_seed", sample=sample, extra=extra),
        default=False,
    ):
        return
    seeded = _copy_seed_files(project, candidates)
    print(t("project_wizard.wiki_seed_done", count=seeded), file=sys.stderr)


def _step_telegram(project: Project, prompter: Prompter) -> None:
    if not _ask_yes_no(prompter, t("project_wizard.ask_telegram"), default=False):
        return
    token_input = prompter(t("project_wizard.ask_telegram_token"), None).strip()
    if not token_input:
        return
    chat_id = prompter(t("project_wizard.ask_telegram_chat"), None).strip()
    if not chat_id:
        print(t("project_wizard.telegram_chat_required"), file=sys.stderr)
        return
    from veles.core.secrets import KeyringUnavailable, set_provider_key

    try:
        set_provider_key("telegram", token_input, project=project.name)
    except KeyringUnavailable as exc:
        print(f"warning: keychain unavailable ({exc}); aborting telegram step", file=sys.stderr)
        return
    cfg = _load_project_toml(project)
    cfg.setdefault("channels", {}).setdefault("telegram", {})
    cfg["channels"]["telegram"]["enabled"] = True
    cfg["channels"]["telegram"]["whitelist"] = [chat_id]
    _save_project_toml(project, cfg)
    print(
        t("project_wizard.telegram_written", path=_project_config_path(project)),
        file=sys.stderr,
    )


# ---------------- helpers ----------------


def _collect_seed_candidates(cwd: Path, *, cap: int = 25) -> list[Path]:
    """README.md + every `*.md` under cwd one level deep + `docs/**/*.md`."""
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
    """Raw copy into `<wiki_root>/sources/seed/<relpath>`. The agent can
    `veles add` (or `/wiki add`) each later; the dream cycle's reindex
    picks up the new pages automatically."""
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
        except OSError as exc:
            print(f"  ! skipping {src}: {exc}", file=sys.stderr)
    if count:
        with contextlib.suppress(OSError):
            Wiki(project.wiki_root).append_log(
                op="seed", summary=f"wizard copied {count} file(s) into sources/seed/"
            )
    return count


def _ask_yes_no(prompter: Prompter, prompt: str, *, default: bool) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    ans = prompter(f"{prompt} {suffix}", "y" if default else "n").strip().lower()
    if not ans:
        return default
    return ans in ("y", "yes")


def _ask_choice(prompter: Prompter, prompt: str, choices: tuple[str, ...], *, default: str) -> str:
    while True:
        ans = prompter(f"{prompt} [{'/'.join(choices)}]", default).strip().lower()
        if not ans:
            return default
        if ans in choices:
            return ans
        print(f"  ! '{ans}' is not one of {choices}; try again.", file=sys.stderr)


def _default_prompter(prompt: str, default: str | None) -> str:
    if not sys.stdin.isatty():
        return default or ""
    label = f"  {prompt}"
    if default is not None:
        label = f"{label} [default: {default}]"
    try:
        return input(f"{label}: ")
    except EOFError:
        return default or ""


def maybe_run_project_wizard(args: argparse.Namespace, cwd: Path) -> Project | None:
    """Safe wrapper. Prefers the TUI flow (M95) when Textual is
    importable; falls back to the stdin flow on any failure or
    headless invocation. Returns the bootstrapped Project on success,
    None when the user declines / cancels or any step explodes."""
    if not should_run_project_wizard(args, cwd):
        return None
    try:
        tui_eligible = sys.stdin.isatty() and sys.stdout.isatty()
        try:
            if not tui_eligible:
                raise ImportError("TUI not eligible in non-interactive shell")
            from veles.tui.wizard.project_runner import run_project_wizard_tui

            # Forward the "user already said Yes" flag set by the first-run
            # wizard so the project-wizard's BootstrapStep skips the
            # duplicate Initialize? confirm screen.
            skip_bootstrap = bool(getattr(args, "_wizard_init_project_here", False))
            # M129: `veles daemon start` runs the wizard but starts the
            # daemon itself afterwards — don't let the wizard autostart a
            # second one (single-instance pid collision).
            autostart_daemon = not getattr(args, "_suppress_wizard_daemon_autostart", False)
            project = run_project_wizard_tui(
                cwd,
                skip_bootstrap_confirm=skip_bootstrap,
                autostart_daemon=autostart_daemon,
            )
            if project is not None:
                return project
            # TUI returned None — either cancelled or user declined the
            # bootstrap. Don't double-prompt via stdin. Mark the conscious
            # decline so main() exits 0 instead of the generic error.
            args._wizard_user_chose_no_project = True
            return None
        except ImportError:
            pass
        except Exception as exc:
            print(
                f"warning: TUI project wizard failed ({type(exc).__name__}: {exc}); "
                "falling back to stdin prompts.",
                file=sys.stderr,
            )
        return run_project_wizard(cwd)
    except KeyboardInterrupt:
        print(
            "\n<project wizard interrupted; partial scaffolding may remain in .veles/>",
            file=sys.stderr,
        )
        return None
    except Exception as exc:
        print(
            f"warning: project wizard failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return None


__all__ = [
    "maybe_run_project_wizard",
    "reset_project_wizard_prompter",
    "run_project_wizard",
    "set_project_wizard_prompter",
    "should_run_project_wizard",
]
