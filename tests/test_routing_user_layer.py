"""M125 — user-level routing layer + `[provider]` base inheritance.

`effective_route` layers project → user → hardcoded, mirroring M124's
`effective_policy`. These tests pin the new layers:

  * project `[provider]` base feeds every ensemble task (footgun fix),
  * user `~/.veles/config.toml` `[routing.tasks]` and `[user]` base,
  * project scope wins over user scope,
  * `embedding` never inherits a chat base.

The autouse `_hermetic_user_home` fixture (conftest) already points
`VELES_USER_HOME` at an empty dir; each test that needs a populated user
home re-points it and writes the file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.project import init_project
from veles.core.project_config import save_project_config
from veles.core.routing import effective_route, route


def _write_user_config(home: Path, body: str) -> None:
    veles_dir = home / ".veles"
    veles_dir.mkdir(parents=True, exist_ok=True)
    (veles_dir / "config.toml").write_text(body, encoding="utf-8")


# ---------- project [provider] base ----------


def test_provider_base_feeds_ensemble_tasks(tmp_path: Path) -> None:
    """The footgun fix: `[provider] default=ollama, model=qwen3` with no
    explicit routes resolves compressor/insights/advisor to ollama, not
    the hardcoded openrouter haiku default."""
    project = init_project(tmp_path / "p", name="p")
    save_project_config(project, {"provider": {"default": "ollama", "model": "qwen3:4b-instruct"}})
    for task in ("compressor", "insights", "advisor", "vision"):
        provider, model, source = effective_route(task, project)
        assert (provider, model) == ("ollama", "qwen3:4b-instruct")
        assert source == "project-provider"


def test_incomplete_provider_base_is_skipped(tmp_path: Path) -> None:
    """`[provider] default` without `model` must NOT synthesize
    `ollama:<openrouter-slug>` — it falls through to DEFAULT_TASKS."""
    project = init_project(tmp_path / "p", name="p")
    save_project_config(project, {"provider": {"default": "ollama"}})
    provider, _model, source = effective_route("compressor", project)
    assert provider == "openrouter"  # DEFAULT_TASKS["compressor"]
    assert source == "default"


def test_explicit_route_beats_provider_base(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    save_project_config(
        project,
        {
            "provider": {"default": "ollama", "model": "qwen3"},
            "routing": {"tasks": {"compressor": "openai:gpt-4o-mini"}},
        },
    )
    assert route("compressor", project) == ("openai", "gpt-4o-mini")
    # advisor has no explicit route → inherits the provider base.
    assert route("advisor", project) == ("ollama", "qwen3")


# ---------- user scope ----------


def test_user_routes_layer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = init_project(tmp_path / "p", name="p")
    home = tmp_path / "home"
    monkeypatch.setenv("VELES_USER_HOME", str(home))
    _write_user_config(
        home,
        '[user]\nlanguage = "en"\ndefault_provider = "openrouter"\n\n'
        '[routing.tasks]\ncompressor = "openai:gpt-4o-mini"\n',
    )
    provider, model, source = effective_route("compressor", project)
    assert (provider, model) == ("openai", "gpt-4o-mini")
    assert source == "user-route"


def test_user_provider_base_layer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = init_project(tmp_path / "p", name="p")
    home = tmp_path / "home"
    monkeypatch.setenv("VELES_USER_HOME", str(home))
    _write_user_config(
        home,
        '[user]\nlanguage = "en"\ndefault_provider = "ollama"\ndefault_model = "qwen3"\n',
    )
    provider, model, source = effective_route("advisor", project)
    assert (provider, model) == ("ollama", "qwen3")
    assert source == "user-provider"


def test_project_scope_beats_user_scope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = init_project(tmp_path / "p", name="p")
    save_project_config(project, {"provider": {"default": "ollama", "model": "qwen3"}})
    home = tmp_path / "home"
    monkeypatch.setenv("VELES_USER_HOME", str(home))
    _write_user_config(
        home,
        '[user]\nlanguage = "en"\ndefault_provider = "openrouter"\n\n'
        '[routing.tasks]\ncompressor = "openai:gpt-4o-mini"\n',
    )
    # project [provider] base (project scope) beats user [routing.tasks].
    provider, model, source = effective_route("compressor", project)
    assert (provider, model) == ("ollama", "qwen3")
    assert source == "project-provider"


# ---------- embedding bypass across scopes ----------


def test_embedding_never_inherits_any_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = init_project(tmp_path / "p", name="p")
    save_project_config(
        project,
        {
            "provider": {"default": "ollama", "model": "qwen3"},
            "routing": {"tasks": {"default": "ollama:qwen3"}},
        },
    )
    home = tmp_path / "home"
    monkeypatch.setenv("VELES_USER_HOME", str(home))
    _write_user_config(
        home,
        '[user]\nlanguage = "en"\ndefault_provider = "ollama"\ndefault_model = "qwen3"\n',
    )
    provider, model, source = effective_route("embedding", project)
    assert (provider, model) == ("openai", "text-embedding-3-small")
    assert source == "default"


def test_embedding_explicit_route_honored(tmp_path: Path) -> None:
    project = init_project(tmp_path / "p", name="p")
    save_project_config(project, {"routing": {"tasks": {"embedding": "ollama:nomic-embed-text"}}})
    assert route("embedding", project) == ("ollama", "nomic-embed-text")


# ---------- end-to-end seam: the route must actually BUILD, not just resolve ----------


def test_compressor_builds_on_local_provider_base(tmp_path: Path) -> None:
    """M125 headline-fix seam: with `[provider] default=ollama` the
    compressor route resolves to ollama AND `build_compressor` must
    actually construct a compressor — `has_api_key` is True for local
    providers, so the route is NOT disabled. Without this, M125 would
    turn the user's 404 into a silently-disabled compressor instead of a
    working local one."""
    from veles.cli._runtime import build_compressor

    project = init_project(tmp_path / "p", name="p")
    save_project_config(project, {"provider": {"default": "ollama", "model": "qwen3:4b-instruct"}})
    # `provider` positional is unused inside (routed independently); pass None.
    compressor = build_compressor(project, None)  # type: ignore[arg-type]
    assert compressor is not None
