"""Tests for the raw-dict user-config readers added in M124-perm-unify.

The dataclass-based `load_user_config()` (UserConfig) is covered by the
existing M47 tests; this file exercises `read_user_config_raw` /
`get_user_section`, which the Permission Engine policy resolver uses
to consume `~/.veles/config.toml [permissions]`.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from veles.core.user_config import (
    get_user_section,
    read_user_config_raw,
    user_config_path,
)
from veles.core.user_paths import USER_HOME_ENV


@pytest.fixture
def isolated_home(monkeypatch, tmp_path: Path) -> Path:
    monkeypatch.setenv(USER_HOME_ENV, str(tmp_path))
    home = tmp_path / ".veles"
    home.mkdir(parents=True, exist_ok=True)
    return home


def test_missing_file_returns_empty_dict(isolated_home: Path) -> None:
    assert read_user_config_raw() == {}


def test_malformed_file_logs_and_returns_empty(
    isolated_home: Path, caplog: pytest.LogCaptureFixture
) -> None:
    user_config_path().write_text("not = valid = toml = here", encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="veles.core.user_config"):
        result = read_user_config_raw()
    assert result == {}
    assert any("ignored" in rec.message for rec in caplog.records)


def test_get_user_section_returns_nested_dict(isolated_home: Path) -> None:
    user_config_path().write_text(
        '[permissions]\nfetch_url = "approval_required"\n', encoding="utf-8"
    )
    section = get_user_section("permissions")
    assert section == {"fetch_url": "approval_required"}


def test_get_user_section_missing_key_returns_empty(isolated_home: Path) -> None:
    user_config_path().write_text('[user]\nlanguage = "ru"\n', encoding="utf-8")
    assert get_user_section("permissions") == {}


def test_read_returns_full_tree(isolated_home: Path) -> None:
    user_config_path().write_text(
        '[user]\nlanguage = "ru"\ndefault_provider = "openrouter"\n'
        '\n[permissions]\nweb_search = "allow"\n',
        encoding="utf-8",
    )
    raw = read_user_config_raw()
    assert raw.get("user", {}).get("language") == "ru"
    assert raw.get("permissions", {}).get("web_search") == "allow"
