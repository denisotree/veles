"""M-R1.3: cascade resolution for effective provider / model."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from veles.cli._parsers._common import DEFAULT_MODEL, DEFAULT_PROVIDER
from veles.core.model_resolver import (
    resolve_effective_model,
    resolve_effective_provider,
)
from veles.core.project import init_project
from veles.core.project_config import save_project_config


@pytest.fixture(autouse=True)
def _isolate_home(tmp_path, monkeypatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "user"))


def _ns(**overrides) -> argparse.Namespace:
    base = {"provider": DEFAULT_PROVIDER, "model": DEFAULT_MODEL}
    base.update(overrides)
    return argparse.Namespace(**base)


# ---- provider cascade ----


def test_explicit_provider_wins(tmp_path: Path) -> None:
    project = init_project(tmp_path, name=None, force=False)
    args = _ns(provider="anthropic")
    assert resolve_effective_provider(args, project) == "anthropic"


def test_project_config_overrides_argparse_default(tmp_path: Path) -> None:
    project = init_project(tmp_path, name=None, force=False)
    save_project_config(project, {"provider": {"default": "openai"}})
    args = _ns()
    assert resolve_effective_provider(args, project) == "openai"


def test_user_config_overrides_when_no_project_provider(tmp_path: Path) -> None:
    project = init_project(tmp_path, name=None, force=False)
    # No project [provider] section — fall through to user config.
    from veles.core.user_config import UserConfig, save_user_config

    save_user_config(UserConfig(language="en", default_provider="gemini"))
    args = _ns()
    assert resolve_effective_provider(args, project) == "gemini"


def test_default_when_nothing_set(tmp_path: Path) -> None:
    project = init_project(tmp_path, name=None, force=False)
    args = _ns()
    assert resolve_effective_provider(args, project) == DEFAULT_PROVIDER


def test_no_project_falls_to_user_then_default(tmp_path: Path) -> None:
    args = _ns()
    assert resolve_effective_provider(args, None) == DEFAULT_PROVIDER


# ---- model cascade ----


def test_explicit_model_wins(tmp_path: Path) -> None:
    project = init_project(tmp_path, name=None, force=False)
    args = _ns(model="custom-model-xyz")
    assert (
        resolve_effective_model(args, project, persisted_model=None)
        == "custom-model-xyz"
    )


def test_persisted_overrides_argparse_default(tmp_path: Path) -> None:
    project = init_project(tmp_path, name=None, force=False)
    args = _ns()  # argparse default
    assert (
        resolve_effective_model(args, project, persisted_model="anthropic/claude-haiku")
        == "anthropic/claude-haiku"
    )


def test_project_config_model_overrides_persisted_and_user(tmp_path: Path) -> None:
    """Wizard's project-scope model pick (saved to `[provider] model` in
    `<project>/.veles/config.toml`) must beat both the per-project
    persisted tui_state and the user-config default. Regression for the
    bug where users picked a model X in the wizard and runs still
    booted on the global last-used model for the provider."""
    project = init_project(tmp_path, name=None, force=False)
    save_project_config(
        project,
        {"provider": {"default": "anthropic", "model": "anthropic/claude-3.7-sonnet"}},
    )
    from veles.core.user_config import UserConfig, save_user_config

    save_user_config(
        UserConfig(language="en", default_provider="openai", default_model="gpt-4o")
    )
    args = _ns()
    assert (
        resolve_effective_model(args, project, persisted_model=None)
        == "anthropic/claude-3.7-sonnet"
    )
    # Even an unrelated persisted_model must not eclipse the project pick.
    assert (
        resolve_effective_model(
            args, project, persisted_model="openrouter/some-other"
        )
        == "anthropic/claude-3.7-sonnet"
    )


def test_user_config_model_used_when_no_persisted(tmp_path: Path) -> None:
    project = init_project(tmp_path, name=None, force=False)
    from veles.core.user_config import UserConfig, save_user_config

    save_user_config(
        UserConfig(language="en", default_provider="openai", default_model="gpt-4o")
    )
    args = _ns()
    assert (
        resolve_effective_model(args, project, persisted_model=None) == "gpt-4o"
    )


def test_default_model_when_nothing_set(tmp_path: Path) -> None:
    args = _ns()
    assert resolve_effective_model(args, None, persisted_model=None) == DEFAULT_MODEL
