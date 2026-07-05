"""Persistence layer for TUI preferences (`tui_state.json`).

The contract is: never raise on a corrupt / missing / mismatched-
version file — return defaults. The TUI must boot. We exercise each
failure mode plus a happy-path round-trip, plus the atomic-write
invariant (no partial files left behind on success).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from veles.core.project import Project
from veles.core.tui_state import (
    TuiPersistentState,
    load_tui_state,
    persist_model_choice,
    save_tui_state,
    tui_state_path,
)


def test_load_returns_defaults_when_file_missing(tmp_path: Path) -> None:
    assert load_tui_state(tmp_path) == TuiPersistentState()


def test_load_returns_defaults_on_corrupt_json(tmp_path: Path) -> None:
    tui_state_path(tmp_path).write_text("not json {", encoding="utf-8")
    assert load_tui_state(tmp_path) == TuiPersistentState()


def test_load_returns_defaults_on_unknown_mode_value(tmp_path: Path) -> None:
    """A persisted unknown mode (older or hand-edited file) → fallback
    to default rather than corrupting AppState with a value the bridge
    can't dispatch."""
    tui_state_path(tmp_path).write_text(
        json.dumps({"version": 1, "mode": "bogus", "active_goal_id": None}),
        encoding="utf-8",
    )
    state = load_tui_state(tmp_path)
    assert state.mode == "auto"


def test_load_returns_defaults_on_version_mismatch(tmp_path: Path) -> None:
    tui_state_path(tmp_path).write_text(
        json.dumps({"version": 99, "mode": "planning"}),
        encoding="utf-8",
    )
    assert load_tui_state(tmp_path) == TuiPersistentState()


def test_load_returns_defaults_on_non_object_payload(tmp_path: Path) -> None:
    tui_state_path(tmp_path).write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    assert load_tui_state(tmp_path) == TuiPersistentState()


def test_save_then_load_round_trips_all_fields(tmp_path: Path) -> None:
    original = TuiPersistentState(mode="goal", active_goal_id="g-42")
    save_tui_state(tmp_path, original)
    assert load_tui_state(tmp_path) == original


def test_save_writes_atomically_no_temp_left_on_success(tmp_path: Path) -> None:
    """Atomic write via tempfile + os.replace: after a clean save, the
    only file under state_dir should be tui_state.json (no `.tmp` leak).
    """
    save_tui_state(tmp_path, TuiPersistentState(mode="planning"))
    survivors = {p.name for p in tmp_path.iterdir()}
    assert survivors == {"tui_state.json"}


def test_save_overwrites_existing_file(tmp_path: Path) -> None:
    save_tui_state(tmp_path, TuiPersistentState(mode="planning"))
    save_tui_state(tmp_path, TuiPersistentState(mode="writing"))
    assert load_tui_state(tmp_path).mode == "writing"


def test_save_creates_parent_dir(tmp_path: Path) -> None:
    nested = tmp_path / "veles_state"
    assert not nested.exists()
    save_tui_state(nested, TuiPersistentState(mode="auto"))
    assert nested.is_dir()
    assert (nested / "tui_state.json").is_file()


def test_load_rejects_non_string_active_goal_id(tmp_path: Path) -> None:
    """Defensive against hand-edited files: only str | None is accepted."""
    tui_state_path(tmp_path).write_text(
        json.dumps({"version": 1, "mode": "auto", "active_goal_id": 42}),
        encoding="utf-8",
    )
    state = load_tui_state(tmp_path)
    assert state.active_goal_id is None


@pytest.mark.parametrize("mode", ["auto", "planning", "writing", "goal"])
def test_all_four_mode_names_round_trip(tmp_path: Path, mode: str) -> None:
    save_tui_state(tmp_path, TuiPersistentState(mode=mode))
    assert load_tui_state(tmp_path).mode == mode


# ---- persist_model_choice: project-config mirror (resolver-cascade fix) ----
#
# `core.model_resolver.resolve_effective_model` puts
# `<project>/.veles/config.toml [engine] model` ABOVE tui_state.json. If
# the wizard wrote a model there, writing only tui_state.json on `/model X`
# would silently lose the user's pick on next boot. `persist_model_choice`
# mirrors the value into project config so the cascade picks the latest
# interactive choice. These tests pin that behaviour (restored from the
# deleted `tests/tui/test_model_persists_on_boot.py`, M187 — the chat-TUI
# tests around them were dropped, but `persist_model_choice` itself is
# still live: called from the REPL `/model` command).


@pytest.fixture
def project(tmp_path: Path) -> Project:
    from veles.core.project import init_project

    return init_project(tmp_path / "proj", name="proj")


def test_persist_model_choice_writes_project_config(project: Project) -> None:
    from veles.core.project_config import load_project_config

    persist_model_choice(project, "openai/gpt-4o")
    cfg = load_project_config(project)
    assert cfg.get("engine", {}).get("model") == "openai/gpt-4o"


def test_persist_model_choice_preserves_other_keys(project: Project) -> None:
    """Pre-seed config with unrelated sections + a provider default; the
    helper must keep them intact while overwriting only `[engine] model`."""
    from veles.core.project_config import load_project_config, save_project_config

    save_project_config(
        project,
        {
            "engine": {"provider": "openrouter", "model": "old-model"},
            "daemon": {"enabled": True, "port": 8765},
        },
    )
    persist_model_choice(project, "anthropic/claude-3.7-sonnet")
    cfg = load_project_config(project)
    assert cfg["engine"]["model"] == "anthropic/claude-3.7-sonnet"
    assert cfg["engine"]["provider"] == "openrouter"
    assert cfg["daemon"] == {"enabled": True, "port": 8765}


def test_persist_model_choice_also_updates_tui_state(project: Project) -> None:
    """Both surfaces stay in sync — tui_state.json keeps its role as a
    fallback when project config doesn't exist yet."""
    save_tui_state(project.state_dir, TuiPersistentState(mode="planning"))
    persist_model_choice(project, "openai/gpt-4o")
    reloaded = load_tui_state(project.state_dir)
    assert reloaded.model == "openai/gpt-4o"
    assert reloaded.mode == "planning"  # untouched
