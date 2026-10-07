"""Where a channel's secrets live and how they are read."""

from __future__ import annotations

from veles.core.channel_setup import resolve_secrets, secret_slot
from veles.core.platforms import CredField, PlatformSpec

_SPEC = PlatformSpec(
    build=lambda ctx: None,  # type: ignore[arg-type,return-value]
    cred_fields=(
        CredField("bot_token", "t", secret=True, required=True, env="X_TOKEN"),
        CredField("app_token", "a", secret=True),
        CredField("whitelist", "w", list_value=True),
    ),
)


def test_primary_secret_keeps_the_bare_slot() -> None:
    """A running bot's token stays where it always was."""
    assert secret_slot(_SPEC, "slackish", "bot_token") == "slackish"


def test_secondary_secret_gets_its_own_slot() -> None:
    assert secret_slot(_SPEC, "slackish", "app_token") == "slackish.app_token"


def test_resolution_order_keychain_config_env(monkeypatch) -> None:
    store = {"slackish": "kc-bot"}
    monkeypatch.setattr("veles.core.secrets.get_provider_key", lambda slot, **kw: store.get(slot))
    monkeypatch.setenv("X_TOKEN", "env-bot")
    values, missing = resolve_secrets(_SPEC, "slackish", {"app_token": "cfg-app"}, project=None)
    assert values == {"bot_token": "kc-bot", "app_token": "cfg-app"} and missing == []
    store.clear()
    values, missing = resolve_secrets(_SPEC, "slackish", {}, project=None)
    assert missing == ["bot_token"]  # the environment only with use_env
    values, _ = resolve_secrets(_SPEC, "slackish", {}, project=None, use_env=True)
    assert values == {"bot_token": "env-bot"}


def test_a_channel_whose_module_failed_to_load_says_why(tmp_path, monkeypatch) -> None:
    """Not "its module isn't installed" — it is, and a missing package broke it."""
    from veles.core.channel_setup import channel_readiness, no_channel_message
    from veles.core.modules import ModuleRegistry, reset_module_registry, set_module_registry
    from veles.core.project import init_project

    project = init_project(tmp_path / "p", name="p")
    (project.state_dir / "config.toml").write_text(
        "[channels.discordish]\nenabled = true\n", encoding="utf-8"
    )
    reg = ModuleRegistry()
    token = set_module_registry(reg)
    try:
        [status] = channel_readiness(project)
        assert (status.state, status.detail) == ("no_module", "its module isn't installed")
        # Another module's failure doesn't make this one "failed to load".
        reg.load_errors["other"] = "failed to import m.py: No module named 'x'"
        [status] = channel_readiness(project)
        assert status.state == "no_module" and "isn't installed" in status.detail
        assert "other" in status.detail and "uv tool install" not in status.detail
        reg.load_errors["discordish"] = "failed to import m.py: No module named 'discord'"
        [status] = channel_readiness(project)
        assert status.state == "load_failed"
        assert "No module named 'discord'" in status.detail
        assert "uv tool install veles-ai --with" in status.detail
        # Reinstalling an installed module doesn't fix its import.
        message = no_channel_message([status], None)
        assert "veles doctor" in message and "registry install" not in message
    finally:
        reset_module_registry(token)


def test_each_secret_reads_its_own_slot(monkeypatch) -> None:
    store = {"slackish": "bot", "slackish.app_token": "app"}
    monkeypatch.setattr("veles.core.secrets.get_provider_key", lambda slot, **kw: store.get(slot))
    values, _ = resolve_secrets(_SPEC, "slackish", {}, project=None)
    assert values == {"bot_token": "bot", "app_token": "app"}
