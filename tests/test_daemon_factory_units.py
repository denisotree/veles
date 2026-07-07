"""M-R2.3: daemon's factory split — `_factory_settings_from_args` +
`_build_agent_for_turn` are testable independently of the closure."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from veles.cli.commands.daemon import (
    _build_agent_for_turn,
    _factory_settings_from_args,
    _FactorySettings,
    _make_agent_factory,
)
from veles.core.context import reset_active_project, set_active_project
from veles.core.memory import SessionStore
from veles.core.project import init_project


def test_factory_settings_extracts_defaults(tmp_path: Path) -> None:
    """Namespace with a model + project without config: documented defaults
    for everything else (provider, budgets, flags)."""
    project = init_project(tmp_path, name=None, force=False)
    s = _factory_settings_from_args(argparse.Namespace(model="test/model"), project)
    assert s.provider_name == "openrouter"
    assert s.model == "test/model"
    assert s.max_tokens == 4096
    assert s.verbose is False
    assert s.no_compress is False
    assert s.skills_cache_ttl == 600.0  # M158-followup default


def test_factory_settings_requires_a_configured_model(tmp_path: Path) -> None:
    """M165: no model anywhere (empty Namespace, no project/user config) ⇒ a
    clear ConfigurationError, never a silent cloud-model fallback."""
    from veles.core.model_resolver import ConfigurationError

    project = init_project(tmp_path, name=None, force=False)
    with pytest.raises(ConfigurationError, match="no model configured"):
        _factory_settings_from_args(argparse.Namespace(), project)


def test_factory_settings_skills_cache_ttl_from_config(tmp_path: Path) -> None:
    """`[daemon] skills_cache_ttl` overrides the 600s default; an explicit 0
    disables the daemon skills cache (re-parse every turn)."""
    from veles.core.project_config import save_project_config

    project = init_project(tmp_path, name=None, force=False)
    save_project_config(project, {"daemon": {"skills_cache_ttl": 900}})
    s = _factory_settings_from_args(argparse.Namespace(model="test/model", provider=None), project)
    assert s.skills_cache_ttl == 900.0

    save_project_config(project, {"daemon": {"skills_cache_ttl": 0}})
    s0 = _factory_settings_from_args(argparse.Namespace(model="test/model", provider=None), project)
    assert s0.skills_cache_ttl == 0.0


def test_factory_settings_compressor_model_defers_to_route(tmp_path: Path) -> None:
    """M125 daemon regression: the `daemon start` parser never registers
    `--compressor-model`, so `_factory_settings_from_args` must default it
    to None (defer to `route("compressor")`), NOT to the haiku constant.

    Before the fix, a fully-local `[engine]=ollama` project still got
    `compressor_model = "anthropic/claude-haiku-4.5"`, which `build_compressor`
    let win over the M125-routed ollama model — the daemon summarised on
    paid haiku despite a local provider."""
    from veles.core.project_config import save_project_config

    project = init_project(tmp_path, name=None, force=False)
    save_project_config(project, {"engine": {"provider": "ollama", "model": "qwen3:4b-instruct"}})
    # The daemon-start parser sets model/provider=None and omits
    # --compressor-model entirely.
    args = argparse.Namespace(model=None, provider=None)
    s = _factory_settings_from_args(args, project)
    assert s.compressor_model is None
    assert s.model == "qwen3:4b-instruct"


def test_factory_settings_honors_explicit_args(tmp_path: Path) -> None:
    project = init_project(tmp_path, name=None, force=False)
    args = argparse.Namespace(
        provider="openai",
        _provider_explicit=True,  # simulate an explicit `--provider openai`
        model="gpt-4o",
        max_iterations=5,
        max_tokens=8192,
        verbose=True,
        no_compress=True,
        compress_threshold_tokens=10_000,
        compressor_model="anthropic/claude-haiku-4.5",
    )
    s = _factory_settings_from_args(args, project)
    assert s.provider_name == "openai"
    assert s.model == "gpt-4o"
    assert s.max_iterations == 5
    assert s.max_tokens == 8192
    assert s.verbose is True
    assert s.no_compress is True
    assert s.compress_threshold == 10_000


def test_factory_settings_reads_project_config_when_cli_absent(tmp_path: Path) -> None:
    """Cascade rung 2: when --model/--provider are absent (None sentinel
    from daemon parser), `[engine]` in <project>/.veles/config.toml wins
    over DEFAULT_MODEL/DEFAULT_PROVIDER. Mirrors the Mind Palace bug
    where the daemon ignored `model = "google/gemini-3.1-pro-preview"`."""
    project = init_project(tmp_path, name=None, force=False)
    cfg_path = project.state_dir / "config.toml"
    cfg_path.write_text(
        '[engine]\nprovider = "openai"\nmodel = "google/gemini-3.1-pro-preview"\n',
        encoding="utf-8",
    )
    args = argparse.Namespace(model=None, provider=None)
    s = _factory_settings_from_args(args, project)
    assert s.model == "google/gemini-3.1-pro-preview"
    assert s.provider_name == "openai"


def test_factory_settings_inherits_user_level_model(tmp_path: Path) -> None:
    """M130 (cascade rung 3): a daemon in a project WITHOUT its own
    `[engine]` must inherit the user-level `[user] default_provider/
    default_model` — the same cascade the TUI uses (`resolve_effective_*`).

    Before the fix `_factory_settings_from_args` read only the project
    `[engine]` (`cfg_model or DEFAULT_MODEL`), so a user who picked
    ollama in the user-level wizard still booted the daemon on
    `anthropic/claude-sonnet-4.6` — a provider/model mismatch (the
    Mind Palace `daemon start` report)."""
    from veles.core.user_config import user_config_path

    cfg_path = user_config_path()  # under the hermetic VELES_USER_HOME
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(
        '[user]\nlanguage = "en"\n'
        'default_provider = "ollama"\n'
        'default_model = "qwen3:4b-instruct"\n',
        encoding="utf-8",
    )
    project = init_project(tmp_path, name=None, force=False)  # no [engine]
    s = _factory_settings_from_args(argparse.Namespace(model=None, provider=None), project)
    assert s.provider_name == "ollama"
    assert s.model == "qwen3:4b-instruct"


def test_factory_settings_project_provider_beats_user_level(tmp_path: Path) -> None:
    """M130: project `[engine]` still wins over the user-level config."""
    from veles.core.user_config import user_config_path

    cfg_path = user_config_path()
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(
        '[user]\nlanguage = "en"\n'
        'default_provider = "ollama"\n'
        'default_model = "qwen3:4b-instruct"\n',
        encoding="utf-8",
    )
    project = init_project(tmp_path, name=None, force=False)
    (project.state_dir / "config.toml").write_text(
        '[engine]\nprovider = "openai"\nmodel = "gpt-4o"\n', encoding="utf-8"
    )
    s = _factory_settings_from_args(argparse.Namespace(model=None, provider=None), project)
    assert s.provider_name == "openai"
    assert s.model == "gpt-4o"


def test_factory_settings_cli_overrides_project_config(tmp_path: Path) -> None:
    """Cascade rung 1: explicit --model on the CLI beats project config."""
    project = init_project(tmp_path, name=None, force=False)
    (project.state_dir / "config.toml").write_text(
        '[engine]\nmodel = "google/gemini-3.1-pro-preview"\n',
        encoding="utf-8",
    )
    args = argparse.Namespace(
        model="anthropic/claude-haiku-4.5", provider="anthropic", _provider_explicit=True
    )
    s = _factory_settings_from_args(args, project)
    assert s.model == "anthropic/claude-haiku-4.5"
    assert s.provider_name == "anthropic"


def test_settings_dataclass_is_frozen() -> None:
    """`_FactorySettings` is frozen — accidental mutation would silently
    desync the per-turn agent from the snapshot taken at startup."""
    import pytest

    s = _FactorySettings(
        provider_name="openrouter",
        model="m",
        max_iterations=1,
        max_tokens=1,
        verbose=False,
        no_compress=False,
        compress_threshold=1,
        compressor_model="m",
        max_summariser_input_tokens=None,
        hard_ceiling_tokens=None,
    )
    with pytest.raises((AttributeError, TypeError)):
        s.model = "other"  # type: ignore[misc]


def test_build_agent_for_turn_uses_settings_model(tmp_path: Path, monkeypatch) -> None:
    """End-to-end smoke: `_build_agent_for_turn` constructs an Agent
    with `settings.model` and the active session id."""
    project = init_project(tmp_path, name=None, force=False)
    token = set_active_project(project)
    try:
        store = SessionStore(project.memory_db_path)

        # Stub the provider+skill machinery so we don't hit OpenRouter.
        captured: dict[str, object] = {}

        class _StubProvider:
            pass

        def _fake_provider(name, model=None):
            return _StubProvider()

        def _fake_load_skills(project, tools, *, provider, model, **_kw):
            return object()

        def _fake_build_run_system_prompt(project, *, prompt="", **_kw):
            return "STUB"

        def _fake_build_compressor(project, provider, **_kw):
            return None

        class _StubAgent:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        import veles.cli as cli_mod
        import veles.core.agent as agent_mod

        monkeypatch.setattr(cli_mod, "_make_provider", _fake_provider)
        monkeypatch.setattr(cli_mod, "_load_skills", _fake_load_skills)
        monkeypatch.setattr(cli_mod, "build_run_system_prompt", _fake_build_run_system_prompt)
        monkeypatch.setattr(cli_mod, "build_compressor", _fake_build_compressor)
        monkeypatch.setattr(agent_mod, "Agent", _StubAgent)

        settings = _FactorySettings(
            provider_name="openrouter",
            model="anthropic/claude-sonnet-4.6",
            max_iterations=3,
            max_tokens=4096,
            verbose=False,
            no_compress=True,
            compress_threshold=50_000,
            compressor_model="anthropic/claude-haiku-4.5",
            max_summariser_input_tokens=None,
            hard_ceiling_tokens=None,
        )
        _build_agent_for_turn(
            settings, project=project, store=store, session_id=None, prompt="hello"
        )
        assert captured.get("model") == "anthropic/claude-sonnet-4.6"
        assert captured.get("max_iterations") == 3
        assert captured.get("system_prompt") == "STUB"
    finally:
        reset_active_project(token)


def test_build_agent_for_turn_reallocates_stale_session_id(tmp_path: Path, monkeypatch) -> None:
    """Channel session maps can hold an id whose row no longer exists
    in the daemon's memory.db (db reset, migration, multi-daemon
    setup). The factory must detect that and allocate a fresh session
    instead of handing the stale id to Agent — otherwise the first
    `append_turn` trips the FK constraint and surfaces as
    `<error: IntegrityError: FOREIGN KEY constraint failed>` over
    Telegram."""
    project = init_project(tmp_path, name=None, force=False)
    token = set_active_project(project)
    try:
        store = SessionStore(project.memory_db_path)

        captured: dict[str, object] = {}

        class _StubProvider:
            pass

        class _StubAgent:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        import veles.cli as cli_mod
        import veles.core.agent as agent_mod

        monkeypatch.setattr(cli_mod, "_make_provider", lambda name, model=None: _StubProvider())
        monkeypatch.setattr(
            cli_mod, "_load_skills", lambda p, t, *, provider, model, **_kw: object()
        )
        monkeypatch.setattr(
            cli_mod, "build_run_system_prompt", lambda p, *, prompt="", **_kw: "STUB"
        )
        monkeypatch.setattr(cli_mod, "build_compressor", lambda p, prov, **_kw: None)
        monkeypatch.setattr(agent_mod, "Agent", _StubAgent)

        settings = _FactorySettings(
            provider_name="openrouter",
            model="m",
            max_iterations=1,
            max_tokens=1,
            verbose=False,
            no_compress=True,
            compress_threshold=1,
            compressor_model="m",
            max_summariser_input_tokens=None,
            hard_ceiling_tokens=None,
        )
        stale = "0000000000-deadbeef"
        assert not store.session_exists(stale)
        _build_agent_for_turn(
            settings,
            project=project,
            store=store,
            session_id=stale,
            prompt="hi",
        )
        used = captured.get("session_id")
        assert isinstance(used, str)
        assert used != stale
        assert store.session_exists(used)
    finally:
        reset_active_project(token)


def test_make_agent_factory_reuses_provider_and_compressor_across_turns(
    tmp_path: Path, monkeypatch
) -> None:
    """M158-followup: the daemon factory builds provider + compressor ONCE
    (warm HTTP connection pool) and reuses them across turns, while the model
    is still threaded into every turn's Agent — so reuse never pins the model.

    This is the same share-provider / per-turn-model shape the TUI factory has
    always used (`tui/__init__.py`); that factory is a separate code path,
    untouched here, so live `/model` switching in the TUI is unaffected."""
    project = init_project(tmp_path, name=None, force=False)
    token = set_active_project(project)
    try:
        store = SessionStore(project.memory_db_path)
        provider_builds = {"n": 0}
        compressor_builds = {"n": 0}
        models_seen: list[str] = []

        class _StubProvider:
            pass

        class _StubAgent:
            def __init__(self, **kwargs):
                models_seen.append(kwargs.get("model"))

        import veles.cli as cli_mod
        import veles.core.agent as agent_mod

        def _count_provider(name, model=None):
            provider_builds["n"] += 1
            return _StubProvider()

        def _count_compressor(project, provider, **_kw):
            compressor_builds["n"] += 1
            return None

        monkeypatch.setattr(cli_mod, "_make_provider", _count_provider)
        monkeypatch.setattr(cli_mod, "build_compressor", _count_compressor)
        monkeypatch.setattr(
            cli_mod, "_load_skills", lambda p, t, *, provider, model, **_kw: object()
        )
        monkeypatch.setattr(
            cli_mod, "build_run_system_prompt", lambda p, *, prompt="", **_kw: "STUB"
        )
        monkeypatch.setattr(agent_mod, "Agent", _StubAgent)

        factory = _make_agent_factory(
            argparse.Namespace(model="test/model", provider=None), project=project, store=store
        )
        for _ in range(3):
            factory(None, prompt="hi")

        # Built once at factory creation, NOT per turn.
        assert provider_builds["n"] == 1
        assert compressor_builds["n"] == 1
        # The model is still handed to every turn's Agent (reuse ≠ pinning).
        assert models_seen == ["test/model"] * 3
    finally:
        reset_active_project(token)
