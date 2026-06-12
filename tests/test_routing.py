"""M43 — ensemble routing: typed config, lookup, persistence (config.toml since M125/M149)."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.project import init_project
from veles.core.project_config import project_config_path
from veles.core.routing import (
    DEFAULT_TASKS,
    load_routing_config,
    parse_spec,
    route,
    set_project_route,
)

# ---------- parse_spec ----------


def test_parse_spec_provider_and_model() -> None:
    assert parse_spec("anthropic:claude-haiku-4-5-20251001") == (
        "anthropic",
        "claude-haiku-4-5-20251001",
    )


def test_parse_spec_openrouter_with_slash() -> None:
    assert parse_spec("openrouter:anthropic/claude-sonnet-4.6") == (
        "openrouter",
        "anthropic/claude-sonnet-4.6",
    )


def test_parse_spec_no_colon_defaults_to_openrouter() -> None:
    assert parse_spec("anthropic/claude-sonnet-4.6") == (
        "openrouter",
        "anthropic/claude-sonnet-4.6",
    )


def test_parse_spec_strips_whitespace() -> None:
    assert parse_spec("  openai : gpt-4o-mini  ") == ("openai", "gpt-4o-mini")


def test_parse_spec_empty_provider_defaults_to_openrouter() -> None:
    assert parse_spec(":gpt-4o-mini") == ("openrouter", "gpt-4o-mini")


def test_parse_spec_empty_model_raises() -> None:
    with pytest.raises(ValueError, match="empty model"):
        parse_spec("anthropic:")


def test_parse_spec_empty_string_raises() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        parse_spec("")


# ---------- load_routing_config ----------


def test_load_returns_empty_when_file_missing(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    config = load_routing_config(project)
    assert config.tasks == {}


def test_load_reads_partial_overrides(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    set_project_route(project, "compressor", "anthropic:claude-haiku-4-5-20251001")
    config = load_routing_config(project)
    assert config.tasks == {"compressor": "anthropic:claude-haiku-4-5-20251001"}


def test_load_skips_entries_without_colon(tmp_path: Path) -> None:
    """Entries that don't look like `<provider>:<model>` are filtered out."""
    project = init_project(tmp_path / "p", name="p")
    set_project_route(project, "broken", "no-colon-here")
    set_project_route(project, "ok", "anthropic:c-h")
    config = load_routing_config(project)
    assert config.tasks == {"ok": "anthropic:c-h"}


def test_load_handles_missing_routing_section(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    config_path = project_config_path(project)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("[other]\nfoo = 1\n", encoding="utf-8")
    config = load_routing_config(project)
    assert config.tasks == {}


# ---------- set_project_route persistence ----------


def test_set_route_round_trip(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    set_project_route(project, "compressor", "anthropic:claude-haiku-4-5-20251001")
    set_project_route(project, "default", "openai:gpt-4o-mini")
    reloaded = load_routing_config(project)
    assert reloaded.tasks == {
        "compressor": "anthropic:claude-haiku-4-5-20251001",
        "default": "openai:gpt-4o-mini",
    }


def test_set_route_writes_config_toml(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    set_project_route(project, "insights", "anthropic:c-h")
    assert project_config_path(project).is_file()
    text = project_config_path(project).read_text(encoding="utf-8")
    assert "anthropic:c-h" in text


# ---------- route() ----------


def test_route_falls_back_to_default_tasks_when_no_override(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    provider, model = route("compressor", project)
    expected = parse_spec(DEFAULT_TASKS["compressor"])
    assert (provider, model) == expected


def test_route_uses_project_override(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    set_project_route(project, "compressor", "anthropic:claude-haiku-4-5-20251001")
    assert route("compressor", project) == ("anthropic", "claude-haiku-4-5-20251001")


def test_route_falls_back_to_project_default_then_to_static(tmp_path: Path) -> None:
    """Unknown task type → project's "default" → DEFAULT_TASKS["default"]."""
    project = init_project(tmp_path / "p", name="p")
    set_project_route(project, "default", "openai:gpt-4o-mini")
    assert route("never-defined-task", project) == ("openai", "gpt-4o-mini")


def test_route_unknown_task_with_no_overrides_uses_static_default(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    expected = parse_spec(DEFAULT_TASKS["default"])
    assert route("absent-task", project) == expected


def test_nl_hint_beats_provider_base(tmp_path: Path) -> None:
    """M125 Conflict-1 regression: a complete `[provider]` base yields a
    spec for every task, but per-task AGENTS.md NL hints must still win —
    so NL sits ABOVE the provider base in the cascade."""
    from veles.core.project_config import save_project_config
    from veles.core.routing import RoutingConfig, save_nl_routing_config

    project = init_project(tmp_path / "p", name="p")
    save_project_config(project, {"provider": {"default": "ollama", "model": "qwen3"}})
    save_nl_routing_config(project, RoutingConfig(tasks={"compressor": "openai:gpt-4o-mini"}))
    # NL wins for compressor; advisor (no NL) inherits the provider base.
    assert route("compressor", project) == ("openai", "gpt-4o-mini")
    assert route("advisor", project) == ("ollama", "qwen3")


# ---------- DEFAULT_TASKS sanity ----------


def test_default_tasks_all_parse_cleanly() -> None:
    """Every entry in DEFAULT_TASKS must be a valid <provider>:<model> spec."""
    for task, spec in DEFAULT_TASKS.items():
        provider, model = parse_spec(spec)
        assert provider, f"task {task!r} has empty provider in {spec!r}"
        assert model, f"task {task!r} has empty model in {spec!r}"


def test_default_tasks_contains_required_entries() -> None:
    expected = {"default", "curator", "compressor", "insights", "skills"}
    assert expected.issubset(set(DEFAULT_TASKS.keys()))
