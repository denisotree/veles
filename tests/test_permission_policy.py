"""Tests for `effective_policy` — project → user → builtin → risk_floor
resolution with destructive-floor protection."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from veles.core.permission.policy import (
    BUILTIN_TOOL_POLICY_OVERRIDES,
    effective_policy,
)
from veles.core.project import init_project
from veles.core.project_config import project_config_path
from veles.core.risk import RiskClass
from veles.core.tools.registry import ToolEntry
from veles.core.user_config import user_config_path
from veles.core.user_paths import USER_HOME_ENV


def _entry(
    name: str = "demo",
    risk: RiskClass | None = RiskClass.NETWORK_OPEN_WORLD,
    sensitive: bool = False,
) -> ToolEntry:
    return ToolEntry(
        name=name,
        description="",
        parameter_schema={},
        handler=lambda: None,
        is_async=False,
        sensitive=sensitive,
        risk_class=risk,
    )


@pytest.fixture
def isolated_home(monkeypatch, tmp_path: Path) -> Path:
    home = tmp_path / "home"
    monkeypatch.setenv(USER_HOME_ENV, str(home))
    (home / ".veles").mkdir(parents=True, exist_ok=True)
    return home / ".veles"


@pytest.fixture
def active_project(tmp_path: Path):
    from veles.core.context import reset_active_project, set_active_project

    root = tmp_path / "proj"
    root.mkdir()
    project = init_project(root, name="t")
    token = set_active_project(project)
    yield project
    reset_active_project(token)


def test_builtin_override_allows_fetch_url_by_default(isolated_home: Path, active_project) -> None:
    """fetch_url is risk-class NETWORK_OPEN_WORLD (floor=approval_required)
    but builtin override sets it to `allow`."""
    assert BUILTIN_TOOL_POLICY_OVERRIDES["fetch_url"] == "allow"
    assert effective_policy(_entry("fetch_url")) == "allow"


def test_builtin_override_allows_search_files(isolated_home: Path, active_project) -> None:
    e = _entry("search_files", risk=RiskClass.SEARCH_ONLY)
    assert effective_policy(e) == "allow"


def test_user_override_tightens_fetch_url(isolated_home: Path, active_project) -> None:
    user_config_path().write_text(
        '[permissions]\nfetch_url = "approval_required"\n', encoding="utf-8"
    )
    assert effective_policy(_entry("fetch_url")) == "approval_required"


def test_project_override_beats_user_override(isolated_home: Path, active_project) -> None:
    user_config_path().write_text(
        '[permissions]\nfetch_url = "approval_required"\n', encoding="utf-8"
    )
    project_config_path(active_project).write_text(
        '[permissions]\nfetch_url = "always_confirm"\n', encoding="utf-8"
    )
    assert effective_policy(_entry("fetch_url")) == "always_confirm"


def test_invalid_override_value_logged_and_ignored(
    isolated_home: Path,
    active_project,
    caplog: pytest.LogCaptureFixture,
) -> None:
    project_config_path(active_project).write_text(
        '[permissions]\nfetch_url = "yes_please"\n', encoding="utf-8"
    )
    with caplog.at_level(logging.WARNING, logger="veles.core.permission.policy"):
        assert effective_policy(_entry("fetch_url")) == "allow"  # builtin
    assert any("invalid value" in rec.message for rec in caplog.records)


def test_destructive_floor_cannot_be_lowered(
    isolated_home: Path,
    active_project,
    caplog: pytest.LogCaptureFixture,
) -> None:
    project_config_path(active_project).write_text(
        '[permissions]\nrm_rf = "allow"\n', encoding="utf-8"
    )
    e = _entry("rm_rf", risk=RiskClass.DESTRUCTIVE)
    with caplog.at_level(logging.WARNING, logger="veles.core.permission.policy"):
        assert effective_policy(e) == "always_confirm"
    assert any("risk floor" in rec.message for rec in caplog.records)


def test_destructive_floor_can_still_be_set_to_always_confirm(
    isolated_home: Path, active_project
) -> None:
    project_config_path(active_project).write_text(
        '[permissions]\nrm_rf = "always_confirm"\n', encoding="utf-8"
    )
    e = _entry("rm_rf", risk=RiskClass.DESTRUCTIVE)
    assert effective_policy(e) == "always_confirm"


def test_tool_with_no_risk_class_defaults_allow(isolated_home: Path, active_project) -> None:
    assert effective_policy(_entry("misc", risk=None)) == "allow"


def test_unknown_tool_with_network_risk_falls_to_floor(isolated_home: Path, active_project) -> None:
    # Not in BUILTIN_TOOL_POLICY_OVERRIDES; no config overrides → risk floor.
    e = _entry("custom_post", risk=RiskClass.NETWORK_OPEN_WORLD)
    assert effective_policy(e) == "approval_required"
