"""Release E: the provider catalogue — builtin TOML, the user's providers.toml,
module contributions."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from tests.conftest import StubProvider
from veles.core.provider_factory import has_api_key, make_provider, needs_api_key
from veles.core.providers import (
    ProviderContext,
    ProviderSpec,
    builtin_ids,
    find_provider,
    get_provider,
    list_providers,
    user_catalog_path,
)


@pytest.fixture(autouse=True)
def _fresh_catalogue_state() -> Iterator[None]:
    """Warnings are said once per process; each test starts from a clean slate."""
    import veles.core.providers as providers

    providers._warned.clear()
    providers._user_cache.clear()
    yield
    providers._warned.clear()
    providers._user_cache.clear()


@contextmanager
def contributing(specs: dict[str, ProviderSpec]) -> Iterator[None]:
    from veles.core.modules import (
        ModuleAPI,
        ModuleRegistry,
        reset_module_registry,
        set_module_registry,
    )

    scratch, registry = ModuleRegistry(), ModuleRegistry()
    api = ModuleAPI(scratch, "fake-providers")
    for name, spec in specs.items():
        api.contribute("provider", name, spec)
    registry.merge_from(scratch, "fake-providers")
    token = set_module_registry(registry)
    try:
        yield
    finally:
        reset_module_registry(token)


def _user_catalogue(text: str) -> Path:
    path = user_catalog_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_builtin_providers_in_wizard_order() -> None:
    assert list_providers()[:9] == [
        "openrouter",
        "anthropic",
        "openai",
        "gemini",
        "claude-cli",
        "codex",
        "ollama",
        "llamacpp",
        "openai-compat",
    ]
    assert builtin_ids() == frozenset(list_providers()[:9])


def test_every_builtin_builds_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    for env in ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.setenv(env, "test-key")
    monkeypatch.setenv("OPENAI_COMPAT_BASE_URL", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("VELES_LOCAL_TOOLS", "0")  # no capability probe over the network
    for name in builtin_ids():
        assert make_provider(name) is not None, name


def test_classification_from_the_catalogue() -> None:
    assert get_provider("claude-cli").wire == "cli"
    assert not needs_api_key("ollama") and not needs_api_key("claude-cli")
    assert needs_api_key("openrouter")
    assert get_provider("gemini").key_env == ("GEMINI_API_KEY", "GOOGLE_API_KEY")
    assert has_api_key("ollama") is True and has_api_key("claude-cli") is False


def test_a_user_openai_api_entry_needs_no_code(
    isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _user_catalogue(
        '[providers.groq]\nlabel = "Groq"\nkind = "openai-api"\n'
        'base_url = "https://api.groq.com/openai/v1"\nkey_env = ["GROQ_API_KEY"]\n'
    )
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    prov = make_provider("groq", model="llama-3.3-70b")
    assert prov.name == "groq"  # `[engine.request.groq]` keys on it
    assert str(prov._client.base_url).rstrip("/") == "https://api.groq.com/openai/v1"
    assert "groq" in list_providers() and get_provider("groq").model_list == "cached"


def test_user_overrides_a_builtin_setting(
    isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _user_catalogue('[providers.openai]\nbase_url = "https://proxy.example/v1"\nkind = "local"\n')
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    prov = make_provider("openai")
    assert str(prov._client.base_url).rstrip("/") == "https://proxy.example/v1"
    assert get_provider("openai").wire == "openai-wire"  # the kind is not overridable


def test_broken_user_catalogue_keeps_the_builtins(
    isolated_user_home: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _user_catalogue("[providers.x\n")
    with caplog.at_level(logging.WARNING):
        assert set(list_providers()) == builtin_ids()
    assert "providers.toml" in caplog.text


def test_an_array_of_providers_is_a_warning_not_a_crash(
    isolated_user_home: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from veles.core.providers import user_catalog_problems

    _user_catalogue('[[providers]]\nname = "groq"\nkind = "openai-api"\n')
    with caplog.at_level(logging.WARNING):
        assert set(list_providers()) == builtin_ids()
    assert "[providers]" in caplog.text
    assert any("[providers]" in p for p in user_catalog_problems())


def test_a_key_env_of_the_wrong_type_skips_the_entry(
    isolated_user_home: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _user_catalogue(
        '[providers.groq]\nkind = "openai-api"\nbase_url = "https://x/v1"\nkey_env = 5\n'
    )
    with caplog.at_level(logging.WARNING):
        assert find_provider("groq") is None
        assert "openrouter" in list_providers()
    assert "groq" in caplog.text and "key_env" in caplog.text


def test_user_entry_cannot_use_a_builtin_only_kind(
    isolated_user_home: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _user_catalogue('[providers.mycli]\nkind = "claude-cli"\n')
    with caplog.at_level(logging.WARNING):
        assert find_provider("mycli") is None
    assert "mycli" in caplog.text


def test_a_module_contributes_a_provider() -> None:
    spec = ProviderSpec(label="Fake", build=lambda ctx: StubProvider(name=ctx.name))
    with contributing({"fakeprov": spec}):
        assert "fakeprov" in list_providers()
        assert make_provider("fakeprov").name == "fakeprov"
        assert has_api_key("fakeprov") is True  # no key_env → no key needed


def test_a_module_cannot_take_a_builtin_id() -> None:
    spec = ProviderSpec(label="Evil", build=lambda ctx: StubProvider())
    with pytest.raises(ValueError, match="reserved"), contributing({"openrouter": spec}):
        pass


def test_the_user_entry_wins_over_a_module(
    isolated_user_home: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _user_catalogue('[providers.dup]\nkind = "local"\nbase_url = "http://127.0.0.1:9/v1"\n')
    spec = ProviderSpec(label="Mod", build=lambda ctx: StubProvider())
    with contributing({"dup": spec}), caplog.at_level(logging.WARNING):
        assert get_provider("dup").wire == "openai-wire"
    assert "dup" in caplog.text


def test_unknown_provider_lists_what_exists() -> None:
    with pytest.raises(KeyError, match="openrouter"):
        get_provider("nope")
    with pytest.raises(ValueError, match="unknown provider"):
        make_provider("nope")


def test_context_carries_the_model_to_local_probes() -> None:
    seen: list[ProviderContext] = []
    spec = ProviderSpec(label="Probe", build=lambda ctx: seen.append(ctx) or StubProvider())
    with contributing({"probe": spec}):
        make_provider("probe", model="m-1")
    assert seen[0].name == "probe" and seen[0].model == "m-1"


def test_a_user_providers_key_env_routes_to_its_slot(
    isolated_user_home: Path, fake_keyring, monkeypatch: pytest.MonkeyPatch
) -> None:
    from veles.core.provider_factory import require_api_key
    from veles.core.secrets import list_known_names, provider_for_env_name, set_provider_key

    _user_catalogue(
        '[providers.groq]\nkind = "openai-api"\n'
        'base_url = "https://api.groq.com/openai/v1"\nkey_env = ["GROQ_API_KEY"]\n'
    )
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert provider_for_env_name("GROQ_API_KEY") == "groq"
    assert "GROQ_API_KEY" in list_known_names() and "GEMINI_API_KEY" in list_known_names()
    set_provider_key("groq", "gsk-keychain")
    assert require_api_key("groq") == "gsk-keychain"


def test_openai_wire_endpoint_for_vision_and_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    from veles.core.providers import openai_wire_endpoint

    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    assert openai_wire_endpoint("openrouter") == ("https://openrouter.ai/api/v1", "or-key")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://10.0.0.5:11434/v1")
    assert openai_wire_endpoint("ollama") == ("http://10.0.0.5:11434/v1", "local")
    monkeypatch.delenv("OPENAI_COMPAT_BASE_URL", raising=False)
    with pytest.raises(ValueError, match="OPENAI_COMPAT_BASE_URL"):
        openai_wire_endpoint("openai-compat")
    with pytest.raises(ValueError, match="OpenAI wire"):
        openai_wire_endpoint("anthropic")


def test_a_missing_key_names_the_command_that_stores_it(
    isolated_user_home: Path, fake_keyring, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """The hint must name the env var — `veles secret set <id>` stores a flat entry
    no provider reads, and `veles secret add` does not exist."""
    from veles.cli._console import ensure_api_key
    from veles.core.provider_factory import require_api_key

    _user_catalogue(
        '[providers.groq]\nkind = "openai-api"\n'
        'base_url = "https://api.groq.com/openai/v1"\nkey_env = ["GROQ_API_KEY"]\n'
    )
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(RuntimeError) as exc:
        require_api_key("groq")
    assert "veles secret set GROQ_API_KEY" in str(exc.value)
    assert "secret add" not in str(exc.value)
    assert ensure_api_key("groq") is False
    assert "veles secret set GROQ_API_KEY" in capsys.readouterr().err


def test_no_base_url_never_falls_back_to_the_sdk_default(
    isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A key for one company must not travel to another's default endpoint."""
    from veles.core.providers import openai_wire_endpoint

    _user_catalogue('[providers.groq]\nkind = "openai-api"\nkey_env = ["GROQ_API_KEY"]\n')
    monkeypatch.setenv("GROQ_API_KEY", "gsk-secret")
    with pytest.raises(ValueError, match="base_url"):
        openai_wire_endpoint("groq")


def test_the_hand_kept_lists_are_gone() -> None:
    import veles.core.provider_factory as pf
    import veles.core.providers as pr

    for name in ("PROVIDER_API_KEY_ENVS", "LOCAL_PROVIDERS", "CLI_PROVIDERS"):
        assert not hasattr(pf, name), name
    for name in ("ALL_PROVIDERS", "PROVIDER_VALUES"):
        assert not hasattr(pr, name), name


def test_vision_follows_the_wire(isolated_user_home: Path) -> None:
    from veles.core.vision import vision_capable

    _user_catalogue('[providers.vllm]\nkind = "local"\nbase_url = "http://127.0.0.1:9/v1"\n')
    assert vision_capable("vllm") and vision_capable("anthropic") and vision_capable("gemini")
    assert not vision_capable("claude-cli") and not vision_capable("nope")
