"""M127: daemon `_make_agent_factory` always builds with the config-derived
`_FactorySettings` — model/provider are fixed at daemon launch and a
per-session override (a leftover `SessionOverrides.model`) is NEVER applied.

Supersedes the M126 suite that asserted overrides took effect.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from veles.cli.commands.daemon import _make_agent_factory
from veles.core.memory import SessionStore
from veles.core.project import init_project
from veles.daemon.auth import TokenStore
from veles.daemon.server import build_state


def _ns(**fields):
    return type("A", (), fields)()


@pytest.fixture()
def project(tmp_path: Path):
    return init_project(tmp_path / "proj", name="proj")


@pytest.fixture()
def store(project):
    return SessionStore(project.memory_db_path)


@pytest.fixture()
def token_store(tmp_path: Path):
    ts = TokenStore.load(tmp_path / "tokens.json")
    ts.add("default")
    return ts


@pytest.fixture()
def state(project, store, token_store):
    return build_state(
        project=project,
        store=store,
        token_store=token_store,
        agent_factory=lambda *a, **kw: None,
    )


def _args(**extras):
    base = dict(
        provider=None,
        model=None,
        max_iterations=10,
        max_tokens=4096,
        verbose=False,
        no_compress=True,
        compress_threshold_tokens=50_000,
        compressor_model="default-compressor",
    )
    base.update(extras)
    return _ns(**base)


def test_factory_uses_config_model_without_state(project, store) -> None:
    captured = {}

    def fake_build(settings, **kw):
        captured["settings"] = settings
        return "built"

    with patch("veles.daemon.agent_factory._build_agent_for_turn", fake_build):
        factory = _make_agent_factory(
            _args(model="config-model", provider="ollama"),
            project=project,
            store=store,
        )
        factory("sess-1", prompt="hi")
    assert captured["settings"].model == "config-model"
    assert captured["settings"].provider_name == "ollama"


def test_factory_ignores_stray_session_override(project, store, state) -> None:
    """Even when a session carries a leftover model/provider override,
    the factory builds with the config model — M127 fixed-at-launch."""
    state.set_overrides("sess-target", model="haiku-leftover", provider="anthropic")

    captured = {}

    def fake_build(settings, **kw):
        captured["settings"] = settings
        return "built"

    with patch("veles.daemon.agent_factory._build_agent_for_turn", fake_build):
        factory = _make_agent_factory(
            _args(model="config-model", provider="ollama"),
            project=project,
            store=store,
            state=state,
        )
        factory("sess-target", prompt="hi")
    assert captured["settings"].model == "config-model"
    assert captured["settings"].provider_name == "ollama"


def test_factory_none_session_id_uses_config_model(project, store, state, monkeypatch) -> None:
    # The factory validates the routed provider's API key before building;
    # CI has none, so inject a dummy (no network call — the build is patched).
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-unused")
    state.set_overrides("any-session", model="should-not-apply")
    captured = {}

    def fake_build(settings, **kw):
        captured["settings"] = settings
        return "built"

    with patch("veles.daemon.agent_factory._build_agent_for_turn", fake_build):
        factory = _make_agent_factory(
            _args(model="config-model"),
            project=project,
            store=store,
            state=state,
        )
        factory(None, prompt="hi")
    assert captured["settings"].model == "config-model"


def test_factory_log_line_shows_config_model_no_overridden_marker(
    project, store, state, caplog
) -> None:
    """The per-turn log names the config model and never says
    `(overridden)` — the override path is gone."""
    state.set_overrides("sess-target", model="haiku-leftover")

    with patch(
        "veles.daemon.agent_factory._build_agent_for_turn",
        lambda settings, **kw: "built",
    ):
        factory = _make_agent_factory(
            _args(model="config-model", provider="ollama"),
            project=project,
            store=store,
            state=state,
        )
        with caplog.at_level("INFO", logger="veles.daemon.agent_factory"):
            factory("sess-target", prompt="hi")
    matched = [
        r
        for r in caplog.records
        if "session=sess-target" in r.message
        and "model=config-model" in r.message
        and "(overridden)" not in r.message
    ]
    assert matched, f"expected config-model log line, got: {[r.message for r in caplog.records]}"
