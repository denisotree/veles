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


def test_each_secret_reads_its_own_slot(monkeypatch) -> None:
    store = {"slackish": "bot", "slackish.app_token": "app"}
    monkeypatch.setattr("veles.core.secrets.get_provider_key", lambda slot, **kw: store.get(slot))
    values, _ = resolve_secrets(_SPEC, "slackish", {}, project=None)
    assert values == {"bot_token": "bot", "app_token": "app"}
