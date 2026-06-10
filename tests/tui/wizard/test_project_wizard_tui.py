"""End-to-end coverage of the project-level TUI wizard."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core import secrets
from veles.tui.wizard.app import WizardApp
from veles.tui.wizard.project_steps import (
    BootstrapStep,
    DaemonModeStep,
    NormalizationStep,
    ProviderOverrideStep,
    RecapStep,
    WikiSeedStep,
    project_wizard_steps,
)


# M-R1.8: FakeKeyring centralised in tests/conftest.py.
from tests.conftest import FakeKeyring as _FakeKeyring


@pytest.fixture(autouse=True)
def _isolate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> _FakeKeyring:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "veles"))
    for env in ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(env, raising=False)
    kr = _FakeKeyring()
    monkeypatch.setattr(secrets, "_keyring", lambda: (kr, kr.errors))
    return kr


@pytest.fixture
def tmp_cwd(tmp_path: Path) -> Path:
    cwd = tmp_path / "proj"
    cwd.mkdir()
    return cwd


async def _drive(steps, keys: list[str], poll: int = 60) -> dict:
    app = WizardApp(steps=steps)
    async with app.run_test() as pilot:
        await pilot.pause()
        for k in keys:
            await pilot.press(k)
            await pilot.pause()
        for _ in range(poll):
            if app.result is not None or app.is_running is False:
                break
            await pilot.pause()
        return dict(app.result or {})


# ---------------- Bootstrap ----------------


async def test_bootstrap_yes_creates_project(tmp_cwd: Path) -> None:
    steps = [BootstrapStep(cwd=tmp_cwd), RecapStep()]
    answers = await _drive(steps, ["y", "enter"])
    project = answers["project"]
    assert project.root == tmp_cwd
    assert (tmp_cwd / ".veles" / "project.toml").is_file()
    assert (tmp_cwd / "AGENTS.md").is_file()


async def test_bootstrap_no_cancels(tmp_cwd: Path) -> None:
    """Declining bootstrap returns CANCEL → WizardCancelled → result is None."""
    steps = [BootstrapStep(cwd=tmp_cwd), RecapStep()]
    app = WizardApp(steps=steps)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        for _ in range(30):
            if not app.is_running:
                break
            await pilot.pause()
    assert app.result in (None, {})


# ---------------- Daemon gating Telegram ----------------


async def test_daemon_no_skips_telegram(tmp_cwd: Path) -> None:
    """Telegram step lives INSIDE DaemonModeStep — declining daemon means
    no Telegram questions appear at all."""
    steps = [BootstrapStep(cwd=tmp_cwd), DaemonModeStep(), RecapStep()]
    keys = ["y",  # bootstrap
            "n",  # daemon? no
            "enter"]  # recap close
    answers = await _drive(steps, keys)
    assert answers["daemon"] is None
    assert answers.get("telegram") is None


async def test_daemon_yes_with_telegram(tmp_cwd: Path) -> None:
    steps = [BootstrapStep(cwd=tmp_cwd), DaemonModeStep(), RecapStep()]
    keys = [
        "y",  # bootstrap
        "y",  # daemon? yes
        "enter",  # host default 127.0.0.1
        "enter",  # port default 8765
        "y",  # telegram? yes
        "t", "o", "k", "e", "n", "enter",  # bot token
        # MultiSelect: items list is empty, so after M106 the freeform
        # Input is focused automatically — no Tab needed.
        "@", "f", "o", "o",
        "ctrl+s",
        "enter",  # recap close
    ]
    answers = await _drive(steps, keys, poll=120)
    assert answers["daemon"] == {"host": "127.0.0.1", "port": 8765, "autostart": True}
    assert answers["telegram"]["whitelist"] == ["@foo"]
    # Token landed in the keychain under project scope.
    project = answers["project"]
    assert secrets.get_provider_key("telegram", project=project.name) == "token"
    # Daemon + telegram settings persisted to .veles/config.toml.
    import tomllib

    with open(project.state_dir / "config.toml", "rb") as fh:
        cfg = tomllib.load(fh)
    assert cfg["daemon"]["enabled"] is True
    assert cfg["daemon"]["host"] == "127.0.0.1"
    assert cfg["daemon"]["port"] == 8765
    assert cfg["daemon"]["autostart"] is True
    assert cfg["channels"]["telegram"]["enabled"] is True
    assert cfg["channels"]["telegram"]["whitelist"] == ["@foo"]


# ---------------- Provider override ----------------


async def test_provider_override_skip(tmp_cwd: Path) -> None:
    steps = [BootstrapStep(cwd=tmp_cwd), ProviderOverrideStep(), RecapStep()]
    answers = await _drive(steps, ["y", "n", "enter"])
    assert answers["provider_override"] is None


# ---------------- Wiki seed ----------------


async def test_wiki_seed_no_says_no(tmp_cwd: Path) -> None:
    """init_project leaves AGENTS.md (+ CLAUDE.md/GEMINI.md symlinks) so
    candidates is non-empty even on a bare directory. The user picks No
    on the seed prompt → count stays 0."""
    steps = [BootstrapStep(cwd=tmp_cwd), WikiSeedStep(cwd=tmp_cwd), RecapStep()]
    answers = await _drive(steps, ["y", "n", "enter"])
    assert answers["wiki_seed_count"] == 0


async def test_wiki_seed_yes_copies(tmp_cwd: Path) -> None:
    (tmp_cwd / "README.md").write_text("hi", encoding="utf-8")
    (tmp_cwd / "DESIGN.md").write_text("design", encoding="utf-8")
    steps = [BootstrapStep(cwd=tmp_cwd), WikiSeedStep(cwd=tmp_cwd), RecapStep()]
    answers = await _drive(steps, ["y", "y", "enter"])
    # README + DESIGN + AGENTS.md (init_project) + CLAUDE.md/GEMINI.md symlinks
    # all match `*.md`. We don't care about the exact count, but the
    # two we explicitly created must be present.
    assert answers["wiki_seed_count"] >= 2
    project = answers["project"]
    seeded = {p.name for p in (project.wiki_root / "sources" / "seed").rglob("*.md")}
    assert {"README.md", "DESIGN.md"}.issubset(seeded)


# ---------------- Normalization (M96 stub) ----------------


async def test_normalization_skipped_when_no_conflict(tmp_cwd: Path) -> None:
    steps = [BootstrapStep(cwd=tmp_cwd), NormalizationStep(), RecapStep()]
    answers = await _drive(steps, ["y", "enter"])
    assert answers["normalization"] == "no-conflict"


async def test_normalization_detects_existing_files(tmp_cwd: Path) -> None:
    (tmp_cwd / "CLAUDE.md").write_text("a", encoding="utf-8")
    (tmp_cwd / "GEMINI.md").write_text("b", encoding="utf-8")
    steps = [BootstrapStep(cwd=tmp_cwd), NormalizationStep(), RecapStep()]
    # init_project creates AGENTS.md as a real file too — so we already
    # have 3 reals: CLAUDE, GEMINI, AGENTS. Answer y to "want merge".
    answers = await _drive(steps, ["y", "y", "enter"])
    norm = answers["normalization"]
    assert isinstance(norm, dict)
    assert set(norm["files"]) >= {"CLAUDE.md", "GEMINI.md"}
    assert norm["wants_merge"] is True


# ---------------- Full project_wizard_steps shape ----------------


def test_project_wizard_steps_order(tmp_cwd: Path) -> None:
    steps = project_wizard_steps(tmp_cwd)
    names = [s.name for s in steps]
    # M117e: layout-picker inserted right after bootstrap so the
    # project's content layout is selected before downstream steps
    # touch wiki / daemon config.
    assert names == [
        "bootstrap",
        "layout-picker",
        "provider_override",
        "agents_md_normalization",
        "wiki_seed",
        "daemon_mode",
        "recap",
    ]
