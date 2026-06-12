"""M-R1.6: single source of truth for `~/.veles/` resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.user_paths import (
    USER_HOME_ENV,
    user_home,
    user_locales_dir,
    user_logs_dir,
    user_skills_dir,
    user_themes_dir,
)


def test_user_home_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(USER_HOME_ENV, raising=False)
    assert user_home() == Path.home() / ".veles"


def test_user_home_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(USER_HOME_ENV, str(tmp_path))
    assert user_home() == tmp_path / ".veles"


def test_subdir_helpers_compose(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(USER_HOME_ENV, str(tmp_path))
    assert user_logs_dir() == tmp_path / ".veles" / "logs"
    assert user_themes_dir() == tmp_path / ".veles" / "themes"
    assert user_locales_dir() == tmp_path / ".veles" / "locales"
    assert user_skills_dir() == tmp_path / ".veles" / "skills"


def test_helpers_do_not_create_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The helpers are pure path math — callers control creation."""
    monkeypatch.setenv(USER_HOME_ENV, str(tmp_path))
    user_home()
    user_logs_dir()
    assert not (tmp_path / ".veles").exists()
