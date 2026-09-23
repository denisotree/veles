"""M266: `[engine] request_timeout_s` / `max_retries` — client parameters a
project can set.

The reported damage: `request_timeout_for("z-ai/glm-5.3-flash")` is 450s and the
SDK retries twice by default, so one turn could run 1350s inside a 900s budget —
and neither number could be overridden. `[engine.request.<provider>]` (M250) is
the request *body*; a timeout is a client parameter and never reached the wire
that way.
"""

from __future__ import annotations

import pytest

from veles.core.config_schema import ConfigError
from veles.core.context import reset_active_project, set_active_project
from veles.core.model_budgets import (
    request_timeout_for,
    resolve_max_retries,
    resolve_request_timeout,
)
from veles.core.project import init_project
from veles.core.project_config import save_project_config

SLOW = "z-ai/glm-5.3-flash"  # the model the report is about: 450s by its name


@pytest.fixture()
def project_with(tmp_path, monkeypatch):
    """Activate a project whose config declares `[engine]`."""
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    tokens: list = []

    def _make(engine: dict | None):
        project = init_project(tmp_path / "proj", name="proj")
        if engine is not None:
            save_project_config(project, {"engine": engine})
        tokens.append(set_active_project(project))
        return project

    yield _make
    for tok in reversed(tokens):
        reset_active_project(tok)


# ---- timeout ----


def test_configured_timeout_beats_the_per_model_default(project_with) -> None:
    project_with({"request_timeout_s": 180})
    assert request_timeout_for(SLOW) == 450.0  # what the name alone would give
    assert resolve_request_timeout(SLOW) == 180.0


def test_no_engine_section_keeps_the_per_model_default(project_with) -> None:
    project_with(None)
    assert resolve_request_timeout(SLOW) == request_timeout_for(SLOW)
    assert resolve_request_timeout("openai/gpt-4o") == 120.0


def test_outside_a_project_falls_through_without_touching_disk() -> None:
    """A sub-agent or the MCP server can build a provider with no active
    project; that must cost nothing and change nothing."""
    assert resolve_request_timeout(SLOW) == request_timeout_for(SLOW)
    assert resolve_max_retries() is None


def test_explicit_argument_beats_the_config(project_with) -> None:
    project_with({"request_timeout_s": 180})
    assert resolve_request_timeout(SLOW, explicit=30.0) == 30.0


@pytest.mark.parametrize("bad", ["fast", 0, -5, True])
def test_a_nonsense_timeout_is_an_error_naming_the_file(project_with, bad) -> None:
    project = project_with({"request_timeout_s": bad})
    with pytest.raises(ConfigError) as excinfo:
        resolve_request_timeout(SLOW)
    assert str(project.state_dir / "config.toml") in str(excinfo.value)


# ---- retries ----


def test_configured_retries_are_returned(project_with) -> None:
    project_with({"max_retries": 1})
    assert resolve_max_retries() == 1


def test_zero_retries_is_a_legitimate_value(project_with) -> None:
    """`0` is the whole point of the knob for a long-running turn — it must not
    be confused with "unset"."""
    project_with({"max_retries": 0})
    assert resolve_max_retries() == 0


def test_unset_retries_leave_the_sdk_default_alone(project_with) -> None:
    project_with({"request_timeout_s": 180})
    assert resolve_max_retries() is None


@pytest.mark.parametrize("bad", ["two", -1, 1.5, True])
def test_a_nonsense_retry_count_is_an_error(project_with, bad) -> None:
    project_with({"max_retries": bad})
    with pytest.raises(ConfigError):
        resolve_max_retries()


# ---- the adapter resolves both on its own ----


def _openrouter(**kwargs):
    from veles.adapters.openrouter import OpenRouterProvider

    return OpenRouterProvider(api_key="sk-test", **kwargs)  # offline: no network here


def test_bare_construction_picks_up_the_config(project_with) -> None:
    """`adapters/cli/mcp_server.py` builds the provider with no arguments at
    all — before M266 that was a flat 120s in bypass of every budget."""
    project_with({"request_timeout_s": 180, "max_retries": 1})
    client = _openrouter()._client
    assert client.timeout == 180.0
    assert client.max_retries == 1


def test_bare_construction_still_honours_the_model_budget(project_with) -> None:
    project_with(None)
    assert _openrouter(model=SLOW)._client.timeout == 450.0


def test_unconfigured_retries_leave_the_sdk_default(project_with) -> None:
    """Unset must mean "whatever the SDK currently does", not a number Veles
    froze — and `0` must be distinguishable from unset."""
    from openai import OpenAI

    sdk_default = OpenAI(api_key="sk-test").max_retries
    project_with(None)
    assert _openrouter()._client.max_retries == sdk_default


def test_explicit_timeout_still_wins_over_the_config(project_with) -> None:
    project_with({"request_timeout_s": 180})
    assert _openrouter(timeout=30.0, model=SLOW)._client.timeout == 30.0


def test_factory_propagates_the_model(project_with, monkeypatch) -> None:
    """`make_provider` used to compute the timeout itself; it now only has to
    hand over the model."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    project_with(None)
    from veles.core.provider_factory import make_provider

    assert make_provider("openrouter", model=SLOW)._client.timeout == 450.0


def test_skill_runtime_propagates_the_model(project_with, monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    project = project_with(None)
    from veles.runtime.assembly import _make_tool_aware_provider

    provider = _make_tool_aware_provider("openrouter", project, skill_model=SLOW)
    assert provider._client.timeout == 450.0
