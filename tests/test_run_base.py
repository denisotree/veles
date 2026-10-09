"""M325: a model chosen for this run is the base for routed side tasks.

The reported failure: `veles run --provider llamacpp --model qwen3.8-27b` in a
project without `[engine]` printed "compressor disabled: no model configured for
routed task 'compressor'" — the model the user had just named was used for the
main loop only. Worse, with a cloud `[engine]` the compressor sent the history to
the cloud while the user had asked for a local model.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from veles.core.context import current_run_base, reset_run_base, set_run_base
from veles.core.model_resolver import run_base
from veles.core.project import Project, init_project
from veles.core.project_config import save_project_config
from veles.core.routing import effective_route


def _args(provider: str | None = None, model: str | None = None) -> argparse.Namespace:
    """What argparse produces: `--provider` sets the explicit marker."""
    ns = argparse.Namespace(provider=provider or "openrouter", model=model or "")
    if provider is not None:
        ns._provider_explicit = True
    return ns


@pytest.fixture()
def project(tmp_path: Path) -> Project:
    return init_project(tmp_path / "p", name="p")


@pytest.fixture()
def base():
    tokens: list = []

    def _set(pair):
        tokens.append(set_run_base(pair))

    yield _set
    for tok in reversed(tokens):
        reset_run_base(tok)


# ---- run_base: only a choice made for this run counts ----


def test_explicit_flags_are_the_run_base(project) -> None:
    assert run_base(_args("llamacpp", "qwen3.8-27b"), project) == ("llamacpp", "qwen3.8-27b")


def test_no_flags_no_run_base(project) -> None:
    """A pair from config is not a run base: routing reads config already, and
    a user default returned here would shadow the user's own task routes."""
    save_project_config(project, {"engine": {"provider": "ollama", "model": "qwen3"}})
    assert run_base(_args(), project) is None


def test_a_model_flag_alone_takes_the_configured_provider(project) -> None:
    save_project_config(project, {"engine": {"provider": "ollama", "model": "qwen3"}})
    assert run_base(_args(model="llama3.2"), project) == ("ollama", "llama3.2")


def test_a_daemon_session_pin_is_a_run_base(project) -> None:
    save_project_config(
        project,
        {
            "engine": {"provider": "openrouter", "model": "z-ai/glm-5.3-flash"},
            "daemon": {"tg": {"provider": "llamacpp", "model": "qwen3.8-27b"}},
        },
    )
    assert run_base(_args(), project, daemon_session="tg") == ("llamacpp", "qwen3.8-27b")
    assert run_base(_args(), project, daemon_session="other") is None


# ---- effective_route with a run base ----


def test_side_tasks_inherit_the_run_base(project, base) -> None:
    base(("llamacpp", "qwen3.8-27b"))
    for task in ("compressor", "insights", "advisor", "default"):
        assert effective_route(task, project) == ("llamacpp", "qwen3.8-27b", "run-base")


def test_the_run_base_beats_a_cloud_engine(project, base) -> None:
    """The privacy half: `--provider llamacpp` must not summarise the history on
    the cloud `[engine]`."""
    save_project_config(project, {"engine": {"provider": "openrouter", "model": "x/y"}})
    base(("llamacpp", "qwen3.8-27b"))
    assert effective_route("compressor", project)[:2] == ("llamacpp", "qwen3.8-27b")


def test_a_project_task_route_still_wins(project, base) -> None:
    save_project_config(project, {"routing": {"tasks": {"compressor": "openrouter:cheap/model"}}})
    base(("llamacpp", "qwen3.8-27b"))
    assert effective_route("compressor", project) == (
        "openrouter",
        "cheap/model",
        "project-route",
    )


def test_embedding_never_inherits_the_run_base(project, base) -> None:
    from veles.core.model_resolver import ConfigurationError

    base(("llamacpp", "qwen3.8-27b"))
    with pytest.raises(ConfigurationError):
        effective_route("embedding", project)


def test_the_compressor_is_built_on_the_run_base(project, base) -> None:
    """End to end for the reported symptom: no `[engine]`, explicit flags — the
    compressor is on, on the run's model."""
    from veles.runtime.run import build_compressor

    base(("llamacpp", "qwen3.8-27b"))
    compressor = build_compressor(project, provider=None)  # type: ignore[arg-type]
    assert compressor is not None


# ---- the CLI sets it for the whole command ----


def test_run_in_project_sets_the_base_for_the_command(project, monkeypatch) -> None:
    from veles import cli

    monkeypatch.setattr("veles.cli._project._resolve_active_project", lambda args: project)
    monkeypatch.setattr("veles.cli._project._load_project_modules", lambda p, *a: None)
    monkeypatch.setattr("veles.core.registry.ensure.ensure_project_extensions", lambda *a, **k: 0)
    monkeypatch.setattr("veles.core.registry.ensure.ensure_routed_providers", lambda p: None)
    seen: list = []
    args = _args("llamacpp", "qwen3.8-27b")
    args.command = "run"
    rc = cli._run_in_project(args, lambda a, p: seen.append(current_run_base()) or 0)
    assert rc == 0
    assert seen == [("llamacpp", "qwen3.8-27b")]
    assert current_run_base() is None  # reset afterwards
