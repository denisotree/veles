"""Persistent UI preferences for the TUI, stored at
`<project>/.veles/tui_state.json`.

Scope is narrow on purpose: per-turn execution mode (and, once GoalMode
lands, the active goal id). AppState fields that are turn-local or
session-local — `busy`, `queue`, `last_assistant_text` — stay in
memory; persisting them across runs would create more confusion than
value.

Errors are absorbed silently: a missing / corrupt / schema-mismatched
file boots into defaults. The TUI must never refuse to start because
of a stale preference file.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from veles.core.project import Project

_FILENAME = "tui_state.json"
_SCHEMA_VERSION = 1
_VALID_MODES = frozenset({"auto", "planning", "writing", "goal"})


@dataclass(slots=True)
class TuiPersistentState:
    mode: str = "auto"
    active_goal_id: str | None = None
    model: str | None = None


def tui_state_path(state_dir: Path) -> Path:
    return state_dir / _FILENAME


def load_tui_state(state_dir: Path) -> TuiPersistentState:
    """Return persisted state, or defaults for any failure mode."""
    path = tui_state_path(state_dir)
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, FileNotFoundError):
        return TuiPersistentState()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return TuiPersistentState()
    if not isinstance(payload, dict):
        return TuiPersistentState()
    if payload.get("version") != _SCHEMA_VERSION:
        return TuiPersistentState()
    mode = payload.get("mode", "auto")
    if mode not in _VALID_MODES:
        mode = "auto"
    active_goal_id = payload.get("active_goal_id")
    if active_goal_id is not None and not isinstance(active_goal_id, str):
        active_goal_id = None
    model = payload.get("model")
    if model is not None and not isinstance(model, str):
        model = None
    return TuiPersistentState(mode=mode, active_goal_id=active_goal_id, model=model)


def save_tui_state(state_dir: Path, state: TuiPersistentState) -> None:
    """Atomic write via tempfile + os.replace. Best-effort: I/O errors
    bubble up so the caller can decide; in practice the TUI swallows
    them (it's a preference, not data)."""
    state_dir.mkdir(parents=True, exist_ok=True)
    target = tui_state_path(state_dir)
    payload = {"version": _SCHEMA_VERSION, **asdict(state)}
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp_name, target)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def load_for_project(project: Project) -> TuiPersistentState:
    return load_tui_state(project.state_dir)


def save_for_project(project: Project, state: TuiPersistentState) -> None:
    save_tui_state(project.state_dir, state)


def persist_model_choice(project: Project, model: str) -> None:
    """Persist an interactive `/model` pick to both surfaces the resolver
    might consult.

    `tui_state.json` already records the choice (per M81) but
    `core.model_resolver.resolve_effective_model` puts the project's
    `[engine] model` in `config.toml` **above** the tui_state value:
    if the first-run wizard wrote a model there, the user's later
    `/model X` would never win on restart. We update `config.toml` too
    so the cascade picks the latest interactive choice.

    Both writes are best-effort — a transient I/O error doesn't roll
    back the in-memory state, and the other persistence path still
    runs so we don't lose both at once."""
    state = load_for_project(project)
    state.model = model
    with contextlib.suppress(OSError):
        save_for_project(project, state)

    from veles.core.project_config import load_project_config, save_project_config

    cfg = load_project_config(project)
    engine_section = cfg.get("engine")
    if not isinstance(engine_section, dict):
        cfg["engine"] = {"model": model}
    else:
        engine_section["model"] = model
    with contextlib.suppress(OSError):
        save_project_config(project, cfg)


__all__ = [
    "TuiPersistentState",
    "load_for_project",
    "load_tui_state",
    "persist_model_choice",
    "save_for_project",
    "save_tui_state",
    "tui_state_path",
]
