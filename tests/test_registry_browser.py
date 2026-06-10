"""Tests for core/registry_browser.py — Tier δ M54."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from veles.core.registry_browser import (
    DEFAULT_MODULES_REGISTRY,
    DEFAULT_SKILLS_REGISTRY,
    RegistryEntry,
    RegistryFetchError,
    load_registry,
    registry_url,
    search,
)


def _write_index(path: Path, entries: list[dict]) -> None:
    path.write_text(json.dumps(entries))


# ---------- registry_url ----------


def test_default_urls_are_set() -> None:
    assert DEFAULT_MODULES_REGISTRY.startswith("https://")
    assert DEFAULT_SKILLS_REGISTRY.startswith("https://")


def test_registry_url_env_overrides_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VELES_MODULES_REGISTRY_URL", "file:///tmp/x.json")
    assert registry_url("modules") == "file:///tmp/x.json"


def test_registry_url_env_overrides_skills(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VELES_SKILLS_REGISTRY_URL", "file:///tmp/y.json")
    assert registry_url("skills") == "file:///tmp/y.json"


def test_registry_url_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="unknown registry kind"):
        registry_url("widgets")


# ---------- load_registry ----------


def test_load_local_file(tmp_path: Path) -> None:
    idx = tmp_path / "index.json"
    _write_index(
        idx,
        [
            {
                "name": "scheduler",
                "description": "Cron-style scheduling.",
                "repo_url": "https://github.com/foo/scheduler",
                "version": "0.1.0",
                "reviewed": True,
                "tags": ["scheduling"],
            }
        ],
    )
    entries = load_registry(str(idx))
    assert len(entries) == 1
    assert entries[0].name == "scheduler"
    assert entries[0].reviewed is True
    assert entries[0].tags == ("scheduling",)


def test_load_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(RegistryFetchError, match="not found"):
        load_registry(str(tmp_path / "nope.json"))


def test_load_invalid_json_raises(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("not json")
    with pytest.raises(RegistryFetchError, match="UTF-8 JSON"):
        load_registry(str(p))


def test_load_non_array_raises(tmp_path: Path) -> None:
    p = tmp_path / "obj.json"
    p.write_text(json.dumps({"not": "an array"}))
    with pytest.raises(RegistryFetchError, match="must be a JSON array"):
        load_registry(str(p))


def test_load_missing_required_field_raises(tmp_path: Path) -> None:
    p = tmp_path / "broken.json"
    _write_index(p, [{"name": "x"}])  # missing repo_url
    with pytest.raises(RegistryFetchError, match="missing required field"):
        load_registry(str(p))


def test_load_defaults_optional_fields(tmp_path: Path) -> None:
    """`description`, `version`, `reviewed`, `tags` all have safe defaults."""
    p = tmp_path / "minimal.json"
    _write_index(p, [{"name": "x", "repo_url": "https://example.com/x"}])
    entries = load_registry(str(p))
    e = entries[0]
    assert e.description == ""
    assert e.version == ""
    assert e.reviewed is False
    assert e.tags == ()


def test_file_uri_scheme(tmp_path: Path) -> None:
    p = tmp_path / "index.json"
    _write_index(p, [{"name": "x", "repo_url": "https://x"}])
    entries = load_registry(f"file://{p}")
    assert entries[0].name == "x"


# ---------- search ----------


def _e(name: str, *, description: str = "", tags: tuple[str, ...] = ()) -> RegistryEntry:
    return RegistryEntry(
        name=name,
        description=description,
        repo_url="https://x",
        version="0.1",
        reviewed=True,
        tags=tags,
    )


def test_search_empty_query_returns_all() -> None:
    entries = [_e("a"), _e("b")]
    assert search(entries, "") == entries
    assert search(entries, "   ") == entries


def test_search_matches_name() -> None:
    entries = [_e("scheduler"), _e("logger")]
    assert [e.name for e in search(entries, "sched")] == ["scheduler"]


def test_search_matches_description() -> None:
    entries = [_e("a", description="background cron"), _e("b", description="logs")]
    assert [e.name for e in search(entries, "cron")] == ["a"]


def test_search_matches_tags() -> None:
    entries = [_e("a", tags=("scheduling",)), _e("b", tags=("logs",))]
    assert [e.name for e in search(entries, "schedul")] == ["a"]


def test_search_is_case_insensitive() -> None:
    entries = [_e("Scheduler", description="HEAVY")]
    assert search(entries, "heavy") == entries
