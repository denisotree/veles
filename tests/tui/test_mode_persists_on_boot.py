"""Pre-existing `tui_state.json` is honoured on TUI boot.

A user who toggled to `planning` yesterday should see `[planning]` in
the status bar on first start today — the load happens inside
`run_tui` (which `cmd_tui` calls). We bypass the CLI layer here and
write the file directly, then construct AppState the way `run_tui` does.
"""

from __future__ import annotations

from veles.core.tui_state import TuiPersistentState, save_tui_state
from veles.tui.state import AppState


def _make_state_after_boot(project) -> AppState:
    """Mirrors the AppState construction in `veles.tui:run_tui` (after
    persistence is loaded). Keeps the test focused on the persistence
    surface instead of dragging in the whole CLI argparse path."""
    from veles.core.tui_state import load_for_project

    persisted = load_for_project(project)
    return AppState(
        session_id=None,
        provider_name="stub",
        model="m",
        mode=persisted.mode,  # type: ignore[arg-type]
        active_goal_id=persisted.active_goal_id,
    )


def test_boot_picks_up_persisted_mode(tmp_project) -> None:
    project, _ = tmp_project
    save_tui_state(project.state_dir, TuiPersistentState(mode="planning"))
    state = _make_state_after_boot(project)
    assert state.mode == "planning"


def test_boot_falls_back_to_auto_when_file_missing(tmp_project) -> None:
    project, _ = tmp_project
    state = _make_state_after_boot(project)
    assert state.mode == "auto"


def test_boot_falls_back_to_auto_on_unknown_mode(tmp_project) -> None:
    """Hand-edited or older `tui_state.json` with a mode the binary
    doesn't understand any more → safe default, no crash."""
    import json

    from veles.core.tui_state import tui_state_path

    project, _ = tmp_project
    tui_state_path(project.state_dir).parent.mkdir(parents=True, exist_ok=True)
    tui_state_path(project.state_dir).write_text(
        json.dumps({"version": 1, "mode": "weird-mode"}),
        encoding="utf-8",
    )
    state = _make_state_after_boot(project)
    assert state.mode == "auto"


def test_boot_preserves_active_goal_id(tmp_project) -> None:
    project, _ = tmp_project
    save_tui_state(
        project.state_dir,
        TuiPersistentState(mode="goal", active_goal_id="g-77"),
    )
    state = _make_state_after_boot(project)
    assert state.mode == "goal"
    assert state.active_goal_id == "g-77"
