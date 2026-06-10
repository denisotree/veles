"""M47 — UserConfig persistence at ~/.veles/config.toml."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.user_config import (
    UserConfig,
    load_user_config,
    save_user_config,
    user_config_path,
)


@pytest.fixture(autouse=True)
def _isolated_user_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("VELES_USER_HOME", str(home))
    return home


def test_user_config_path_uses_env_override(tmp_path: Path) -> None:
    expected = (tmp_path / "home") / ".veles" / "config.toml"
    assert user_config_path() == expected


def test_load_returns_none_when_missing() -> None:
    assert load_user_config() is None


def test_load_returns_none_for_corrupt_toml(tmp_path: Path) -> None:
    p = user_config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("not a [valid toml", encoding="utf-8")
    assert load_user_config() is None


def test_load_returns_none_when_section_missing() -> None:
    p = user_config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("[other]\nfoo = 1\n", encoding="utf-8")
    assert load_user_config() is None


def test_load_returns_none_when_required_field_missing() -> None:
    p = user_config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('[user]\nlanguage = "en"\n', encoding="utf-8")
    assert load_user_config() is None


def test_save_then_load_round_trip() -> None:
    cfg = UserConfig(
        language="ru",
        default_provider="anthropic",
        first_project_name="myorg",
    )
    save_user_config(cfg)
    loaded = load_user_config()
    assert loaded == cfg


def test_default_model_round_trips() -> None:
    cfg = UserConfig(
        language="en",
        default_provider="openrouter",
        default_model="anthropic/claude-sonnet-4.6",
    )
    save_user_config(cfg)
    loaded = load_user_config()
    assert loaded is not None
    assert loaded.default_model == "anthropic/claude-sonnet-4.6"


def test_default_model_omitted_when_none() -> None:
    cfg = UserConfig(language="en", default_provider="openrouter")
    save_user_config(cfg)
    body = user_config_path().read_text(encoding="utf-8")
    assert "default_model" not in body
    loaded = load_user_config()
    assert loaded is not None
    assert loaded.default_model is None


def test_save_omits_first_project_name_when_blank() -> None:
    cfg = UserConfig(language="en", default_provider="openrouter")
    save_user_config(cfg)
    body = user_config_path().read_text(encoding="utf-8")
    assert "first_project_name" not in body
    loaded = load_user_config()
    assert loaded is not None
    assert loaded.first_project_name is None


def test_save_creates_parent_directory(tmp_path: Path) -> None:
    """The first invocation has to create `.veles/` under the home dir."""
    target = user_config_path()
    assert not target.parent.exists()
    save_user_config(UserConfig(language="en", default_provider="openrouter"))
    assert target.is_file()


def test_save_is_atomic_replaces_existing() -> None:
    """save_user_config overwrites prior contents in-place."""
    save_user_config(UserConfig(language="en", default_provider="openrouter"))
    save_user_config(UserConfig(language="ru", default_provider="anthropic"))
    cfg = load_user_config()
    assert cfg is not None
    assert cfg.language == "ru"
    assert cfg.default_provider == "anthropic"
