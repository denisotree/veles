"""M43b — NL override parsing + persistence + resolution precedence."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.project import Project, init_project
from veles.core.routing import (
    RoutingConfig,
    agents_md_sha256,
    load_nl_routing_config,
    load_nl_state,
    refresh_nl_routing,
    route,
    save_nl_routing_config,
    set_project_route,
)
from veles.core.routing.nl_override import (
    _NLEntry,
    entries_to_routing_config,
    find_routing_hints,
    parse_extractor_output,
)


@pytest.fixture()
def project(tmp_path: Path) -> Project:
    return init_project(tmp_path / "demo", name="demo")


# ---- find_routing_hints ----


def test_find_hints_empty_input() -> None:
    assert find_routing_hints("") == []
    assert find_routing_hints("   \n  \n") == []


def test_find_hints_captures_routing_section() -> None:
    text = (
        "# Project\n\n"
        "## Layout\n\nsources/wiki/...\n\n"
        "## Routing\n\n"
        "Use Opus for planning. Default to Sonnet otherwise.\n\n"
        "## Conventions\n\nKebab-case slugs.\n"
    )
    out = find_routing_hints(text)
    assert len(out) == 1
    assert "Opus for planning" in out[0]
    # The unrelated Layout/Conventions sections should NOT be there.
    assert "Layout" not in out[0]
    assert "Kebab-case" not in out[0]


def test_find_hints_captures_models_section() -> None:
    text = "## Models\n\nUse haiku for compression.\n"
    out = find_routing_hints(text)
    assert len(out) == 1
    assert "haiku" in out[0]


def test_find_hints_inline_fallback() -> None:
    """When no recognised section heading exists, scan top-level lines for hints."""
    text = (
        "Random project notes.\n"
        "Always use opus for plan steps.\n"
        "Some unrelated paragraph about cats and beanbags.\n"
    )
    out = find_routing_hints(text)
    assert len(out) == 1
    assert "opus for plan steps" in out[0]


def test_find_hints_dedupes() -> None:
    text = "## Routing\n\nUse opus for planning.\n\n## Models\n\nUse opus for planning.\n"
    out = find_routing_hints(text)
    assert len(out) == 2  # different section headings = different chunks


# ---- parse_extractor_output ----


def test_parse_strict_json() -> None:
    raw = (
        '{"entries": [{"task": "default", "provider": "anthropic", "model": "claude-sonnet-4-6"}]}'
    )
    out = parse_extractor_output(raw)
    assert out == [_NLEntry(task="default", provider="anthropic", model="claude-sonnet-4-6")]


def test_parse_strips_fences() -> None:
    raw = (
        '```json\n{"entries": [{"task": "compressor", "provider": "anthropic", '
        '"model": "claude-haiku-4-5"}]}\n```'
    )
    out = parse_extractor_output(raw)
    assert len(out) == 1
    assert out[0].task == "compressor"


def test_parse_drops_unknown_task() -> None:
    raw = '{"entries": [{"task": "made-up-task", "provider": "anthropic", "model": "x"}]}'
    assert parse_extractor_output(raw) == []


def test_parse_drops_unknown_provider() -> None:
    raw = '{"entries": [{"task": "default", "provider": "rando", "model": "x"}]}'
    assert parse_extractor_output(raw) == []


def test_parse_drops_empty_model() -> None:
    raw = '{"entries": [{"task": "default", "provider": "anthropic", "model": "  "}]}'
    assert parse_extractor_output(raw) == []


def test_parse_tolerates_garbage() -> None:
    assert parse_extractor_output("") == []
    assert parse_extractor_output("not json at all") == []
    assert parse_extractor_output("[]") == []  # top-level array, not object


def test_parse_mixes_good_and_bad_entries() -> None:
    raw = (
        '{"entries": ['
        '{"task": "default", "provider": "anthropic", "model": "claude-sonnet-4-6"},'
        '{"task": "bogus", "provider": "anthropic", "model": "x"},'
        '{"task": "compressor", "provider": "anthropic", "model": "claude-haiku-4-5"}'
        "]}"
    )
    out = parse_extractor_output(raw)
    assert [e.task for e in out] == ["default", "compressor"]


# ---- entries_to_routing_config ----


def test_entries_later_wins_same_task() -> None:
    entries = [
        _NLEntry(task="default", provider="anthropic", model="claude-sonnet-4-6"),
        _NLEntry(task="default", provider="openai", model="gpt-4o"),
    ]
    cfg = entries_to_routing_config(entries)
    assert cfg.tasks["default"] == "openai:gpt-4o"


def test_entries_empty_produces_empty_config() -> None:
    cfg = entries_to_routing_config([])
    assert cfg.tasks == {}


# ---- precedence ----


def test_default_when_no_files(project: Project) -> None:
    assert route("default", project) == ("openrouter", "anthropic/claude-sonnet-4.6")


def test_nl_overrides_default(project: Project) -> None:
    save_nl_routing_config(
        project, RoutingConfig(tasks={"compressor": "anthropic:claude-haiku-99"})
    )
    assert route("compressor", project) == ("anthropic", "claude-haiku-99")


def test_manual_overrides_nl(project: Project) -> None:
    save_nl_routing_config(project, RoutingConfig(tasks={"compressor": "anthropic:nl-haiku"}))
    set_project_route(project, "compressor", "anthropic:manual-haiku")
    assert route("compressor", project) == ("anthropic", "manual-haiku")


def test_nl_default_used_for_unknown_task(project: Project) -> None:
    """nl-default is a *user-stated* preference for tasks the user hasn't pinned.

    Resolution order in route(): manual-task → manual-default → nl-task →
    nl-default → DEFAULT_TASKS[task] → DEFAULT_TASKS['default']. So an
    nl-default *does* shadow DEFAULT_TASKS for tasks not explicitly set
    anywhere — that's the user's stated preference winning over a hardcoded
    fallback, which is the intended behaviour.
    """
    save_nl_routing_config(project, RoutingConfig(tasks={"default": "openai:gpt-4o"}))
    # advisor isn't manually set; nl-default applies (user-stated > hardcoded).
    assert route("advisor", project) == ("openai", "gpt-4o")
    # "default" itself: same nl-default.
    assert route("default", project) == ("openai", "gpt-4o")


def test_nl_per_task_does_not_leak_to_other_tasks(project: Project) -> None:
    """Setting only `compressor` in nl-toml must NOT touch other tasks."""
    save_nl_routing_config(project, RoutingConfig(tasks={"compressor": "openai:gpt-4o-mini"}))
    assert route("compressor", project) == ("openai", "gpt-4o-mini")
    # advisor falls through to DEFAULT_TASKS.
    assert route("advisor", project) == ("openrouter", "anthropic/claude-sonnet-4.6")


# ---- refresh_nl_routing ----


def test_refresh_writes_state_and_toml(project: Project) -> None:
    text = "## Routing\n\nUse haiku for compression.\n"
    captured: list[_NLEntry] = [
        _NLEntry(task="compressor", provider="anthropic", model="claude-haiku-4-5")
    ]
    state = refresh_nl_routing(project, text, extractor=lambda _t: captured)
    assert state.entries_count == 1
    cfg = load_nl_routing_config(project)
    assert cfg.tasks["compressor"] == "anthropic:claude-haiku-4-5"
    assert load_nl_state(project).agents_md_sha256 == agents_md_sha256(text)


def test_refresh_skips_when_sha_matches(project: Project) -> None:
    text = "## Routing\n\nUse haiku for compression.\n"
    calls = {"n": 0}

    def extractor(_t: str) -> list[_NLEntry]:
        calls["n"] += 1
        return [_NLEntry(task="compressor", provider="anthropic", model="claude-haiku-4-5")]

    refresh_nl_routing(project, text, extractor=extractor)
    assert calls["n"] == 1
    refresh_nl_routing(project, text, extractor=extractor)
    assert calls["n"] == 1  # short-circuited by SHA match


def test_refresh_force_reruns(project: Project) -> None:
    text = "## Routing\n\nUse haiku for compression.\n"
    calls = {"n": 0}

    def extractor(_t: str) -> list[_NLEntry]:
        calls["n"] += 1
        return []

    refresh_nl_routing(project, text, extractor=extractor)
    refresh_nl_routing(project, text, extractor=extractor, force=True)
    assert calls["n"] == 2


def test_refresh_persists_empty_entries(project: Project) -> None:
    """Empty parse still writes an empty TOML so resolution is explicit."""
    text = "no routing section here\n"
    state = refresh_nl_routing(project, text, extractor=lambda _t: [])
    assert state.entries_count == 0
    cfg = load_nl_routing_config(project)
    assert cfg.tasks == {}


def test_refresh_changing_agents_md_reruns(project: Project) -> None:
    extractor_calls: list[str] = []

    def extractor(text: str) -> list[_NLEntry]:
        extractor_calls.append(text)
        return []

    refresh_nl_routing(project, "## Routing\n\nVersion 1\n", extractor=extractor)
    refresh_nl_routing(project, "## Routing\n\nVersion 2\n", extractor=extractor)
    assert len(extractor_calls) == 2
    # Second call sees the new text.
    assert "Version 2" in extractor_calls[1]


def test_state_load_permissive_on_corrupt_json(project: Project, tmp_path: Path) -> None:
    from veles.core.routing import nl_state_path

    path = nl_state_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json", encoding="utf-8")
    state = load_nl_state(project)
    assert state.agents_md_sha256 == ""
    assert state.parsed_at == 0.0


def test_nl_config_load_permissive_on_corrupt_toml(project: Project) -> None:
    from veles.core.routing import nl_routing_path

    path = nl_routing_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not valid toml [[[", encoding="utf-8")
    cfg = load_nl_routing_config(project)
    assert cfg.tasks == {}
