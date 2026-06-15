"""M43 — ensemble routing: typed config, lookup, persistence (config.toml since M125/M149)."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.project import init_project
from veles.core.project_config import project_config_path
from veles.core.routing import (
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


def test_route_raises_when_unconfigured(tmp_path: Path) -> None:
    """M165c: no cloud fallback — an unconfigured chat task raises clearly."""
    from veles.core.model_resolver import ConfigurationError

    project = init_project(tmp_path / "p", name="p")
    with pytest.raises(ConfigurationError, match="no model configured"):
        route("compressor", project)


def test_route_uses_project_override(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    set_project_route(project, "compressor", "anthropic:claude-haiku-4-5-20251001")
    assert route("compressor", project) == ("anthropic", "claude-haiku-4-5-20251001")


def test_route_falls_back_to_project_default(tmp_path: Path) -> None:
    """An unknown task type resolves to the project's `default` route."""
    project = init_project(tmp_path / "p", name="p")
    set_project_route(project, "default", "openai:gpt-4o-mini")
    assert route("never-defined-task", project) == ("openai", "gpt-4o-mini")


def test_route_unknown_task_with_no_overrides_raises(tmp_path: Path) -> None:
    from veles.core.model_resolver import ConfigurationError

    project = init_project(tmp_path / "p", name="p")
    with pytest.raises(ConfigurationError):
        route("absent-task", project)


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


# ---------- task set + embedding (M165d: no hardcoded defaults) ----------


def test_known_tasks_contains_required_entries() -> None:
    from veles.core.routing import KNOWN_TASKS

    assert {
        "default",
        "curator",
        "compressor",
        "insights",
        "skills",
        "advisor",
        "vision",
        "embedding",
    }.issubset(KNOWN_TASKS)


def test_route_embedding_raises_when_unconfigured(tmp_path: Path) -> None:
    """M165d: `embedding` has no hardcoded default — it raises like any task
    when no explicit `[routing.tasks].embedding` is set (the base never feeds
    it; a chat model is not an embedding model)."""
    from veles.core.model_resolver import ConfigurationError

    project = init_project(tmp_path / "p", name="p")
    # A `[provider]` base must NOT satisfy embedding (bypass).
    from veles.core.project_config import save_project_config

    save_project_config(project, {"provider": {"default": "ollama", "model": "qwen3"}})
    with pytest.raises(ConfigurationError):
        route("embedding", project)


def test_route_embedding_resolves_from_explicit_route(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    set_project_route(project, "embedding", "openai:text-embedding-3-small")
    assert route("embedding", project) == ("openai", "text-embedding-3-small")
