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

from veles.core.tui_state import (
    TuiPersistentState,
    load_tui_state,
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
