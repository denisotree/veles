"""M107: when `veles tui` runs without an explicit `--provider`, the
status bar must reflect the *actual* provider the user configured —
either via the project's `.veles/config.toml` or the user-level
wizard — not the argparse default.
"""

from __future__ import annotations

from pathlib import Path

from veles.core.project import init_project
from veles.tui import _load_project_default_provider


def test_load_project_provider_missing_config(tmp_path: Path) -> None:
    project = init_project(tmp_path, name=None, force=False)
    # No config.toml written — helper returns None so the caller can
    # cascade to user-level config.
    assert _load_project_default_provider(project) is None


def test_load_project_provider_present(tmp_path: Path) -> None:
    project = init_project(tmp_path, name=None, force=False)
    (project.state_dir / "config.toml").write_text(
        '[provider]\ndefault = "openai"\n',
        encoding="utf-8",
    )
    assert _load_project_default_provider(project) == "openai"


def test_load_project_provider_no_provider_section(tmp_path: Path) -> None:
    project = init_project(tmp_path, name=None, force=False)
    (project.state_dir / "config.toml").write_text(
        "[daemon]\nenabled = true\n",
        encoding="utf-8",
    )
    assert _load_project_default_provider(project) is None


def test_load_project_provider_malformed_toml(tmp_path: Path) -> None:
    project = init_project(tmp_path, name=None, force=False)
    (project.state_dir / "config.toml").write_text("not valid toml [[[", encoding="utf-8")
    # Malformed file is treated as absent — no crash.
    assert _load_project_default_provider(project) is None
