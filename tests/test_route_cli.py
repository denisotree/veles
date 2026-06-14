"""M125 — `veles route` writes/reads config.toml.

`set`/`reset` read-modify-write `config.toml [routing.tasks]` (no
standalone routing.toml since M149); `show` resolves through
`effective_route` and prints a source label per task.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from veles.cli.commands.route import _reset, _set, _show
from veles.core.project import init_project
from veles.core.project_config import get_section, load_project_config


def _ns(**kw: object) -> argparse.Namespace:
    return argparse.Namespace(**kw)


# ---------- set ----------


def test_set_writes_config_toml_routing_tasks(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    rc = _set(_ns(task="compressor", spec="ollama:qwen3"), project)
    assert rc == 0
    assert not (project.state_dir / "routing.toml").is_file()  # NOT a standalone file
    tasks = get_section(load_project_config(project), "routing", "tasks")
    assert tasks == {"compressor": "ollama:qwen3"}


def test_set_preserves_other_sections(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    from veles.core.project_config import save_project_config

    save_project_config(project, {"provider": {"default": "ollama", "model": "qwen3"}})
    _set(_ns(task="advisor", spec="openrouter:anthropic/claude-opus-4.8"), project)
    cfg = load_project_config(project)
    assert cfg["provider"] == {"default": "ollama", "model": "qwen3"}
    assert get_section(cfg, "routing", "tasks") == {
        "advisor": "openrouter:anthropic/claude-opus-4.8"
    }


def test_set_rejects_empty_model(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    rc = _set(_ns(task="compressor", spec="anthropic:"), project)
    assert rc == 2
    assert get_section(load_project_config(project), "routing", "tasks") == {}


# ---------- reset ----------


def test_reset_single_task(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    _set(_ns(task="compressor", spec="ollama:qwen3"), project)
    _set(_ns(task="advisor", spec="ollama:qwen3"), project)
    rc = _reset(_ns(task="compressor"), project)
    assert rc == 0
    assert get_section(load_project_config(project), "routing", "tasks") == {
        "advisor": "ollama:qwen3"
    }


def test_reset_all(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    _set(_ns(task="compressor", spec="ollama:qwen3"), project)
    rc = _reset(_ns(task=None), project)
    assert rc == 0
    assert get_section(load_project_config(project), "routing", "tasks") == {}


def test_reset_absent_task_is_noop(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    project = init_project(tmp_path / "p", name="p")
    rc = _reset(_ns(task="compressor"), project)
    assert rc == 0
    assert "already at default" in capsys.readouterr().err


# ---------- show ----------


def test_show_prints_source_labels(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    project = init_project(tmp_path / "p", name="p")
    from veles.core.project_config import save_project_config

    save_project_config(project, {"provider": {"default": "ollama", "model": "qwen3"}})
    _set(_ns(task="compressor", spec="openai:gpt-4o-mini"), project)
    rc = _show(project)
    out = capsys.readouterr().out
    assert rc == 0
    # explicit route → project-route; inherited → project-provider;
    # embedding bypasses the base → default.
    assert "compressor" in out and "openai:gpt-4o-mini" in out and "project-route" in out
    assert "project-provider" in out  # e.g. advisor inherits ollama:qwen3
    assert "ollama:qwen3" in out
    assert "openai:text-embedding-3-small" in out  # embedding default


def test_show_warns_on_incomplete_provider(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = init_project(tmp_path / "p", name="p")
    from veles.core.project_config import save_project_config

    save_project_config(project, {"provider": {"default": "ollama"}})
    _show(project)
    assert "has no model" in capsys.readouterr().err


def test_leftover_routing_toml_is_ignored(tmp_path: Path) -> None:
    """M149: a leftover standalone routing.toml has no effect — config.toml
    is the single source of truth."""
    project = init_project(tmp_path / "p", name="p")
    (project.state_dir / "routing.toml").write_text(
        '[routing.tasks]\ncompressor = "ollama:qwen3"\n', encoding="utf-8"
    )
    from veles.core.model_resolver import ConfigurationError
    from veles.core.routing import route

    # The leftover routing.toml is ignored, so compressor is unconfigured and
    # routing raises (M165c) — proving config.toml is the only source.
    with pytest.raises(ConfigurationError):
        route("compressor", project)
