"""M-R1.2: single loader/saver for `<project>/.veles/config.toml`.

Replaces ad-hoc `tomllib.load(open(state_dir/'config.toml', 'rb'))`
patterns that lived in tui/__init__.py, daemon/server.py,
cli/project_wizard.py, and tui/wizard/project_steps.py.
"""

from __future__ import annotations

from pathlib import Path

from veles.core.project import init_project
from veles.core.project_config import (
    get_section,
    load_project_config,
    project_config_path,
    save_project_config,
)


def test_load_missing_returns_empty_dict(tmp_path: Path) -> None:
    project = init_project(tmp_path, name=None, force=False)
    assert load_project_config(project) == {}


def test_load_malformed_returns_empty_dict(tmp_path: Path) -> None:
    project = init_project(tmp_path, name=None, force=False)
    project_config_path(project).write_text("not [[[ valid toml", encoding="utf-8")
    assert load_project_config(project) == {}


def test_round_trip_provider_section(tmp_path: Path) -> None:
    project = init_project(tmp_path, name=None, force=False)
    save_project_config(project, {"engine": {"provider": "openai"}})
    cfg = load_project_config(project)
    assert cfg["engine"]["provider"] == "openai"


def test_round_trip_preserves_list_and_bool(tmp_path: Path) -> None:
    project = init_project(tmp_path, name=None, force=False)
    save_project_config(
        project,
        {
            "channels": {
                "telegram": {
                    "enabled": True,
                    "whitelist": ["@alice", "12345"],
                }
            }
        },
    )
    cfg = load_project_config(project)
    tg = cfg["channels"]["telegram"]
    assert tg["enabled"] is True
    assert tg["whitelist"] == ["@alice", "12345"]


def test_get_section_nested(tmp_path: Path) -> None:
    project = init_project(tmp_path, name=None, force=False)
    save_project_config(
        project,
        {"channels": {"telegram": {"enabled": True}}},
    )
    cfg = load_project_config(project)
    assert get_section(cfg, "channels", "telegram") == {"enabled": True}


def test_get_section_missing_returns_empty(tmp_path: Path) -> None:
    project = init_project(tmp_path, name=None, force=False)
    cfg = load_project_config(project)
    assert get_section(cfg, "no", "such", "path") == {}


def test_get_section_on_wrong_type(tmp_path: Path) -> None:
    """If a path segment exists but isn't a dict, get_section returns {}
    instead of raising — protects against malformed configs."""
    project = init_project(tmp_path, name=None, force=False)
    save_project_config(project, {"engine": {"provider": "openai"}})
    cfg = load_project_config(project)
    # `engine.provider` is a string, not a dict → get_section bottoms out.
    assert get_section(cfg, "engine", "provider") == {}


def test_save_creates_state_dir_if_missing(tmp_path: Path) -> None:
    """Calling save before init was called manually — directory created
    on the fly (defensive; the wizard always init's first)."""
    project = init_project(tmp_path, name=None, force=False)
    # Wipe the state_dir to ensure save_project_config re-creates it.
    import shutil

    shutil.rmtree(project.state_dir)
    save_project_config(project, {"k": "v"})
    assert project_config_path(project).is_file()
