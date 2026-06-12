"""M92: per-project credentials — scope > default > env lookup."""

from __future__ import annotations

from pathlib import Path

import pytest

# M-R1.8: FakeKeyring + fake_keyring fixture live in tests/conftest.py.
from tests.conftest import FakeKeyring as _FakeKeyring
from veles.core import secrets


@pytest.fixture
def fake_kr(fake_keyring: _FakeKeyring) -> _FakeKeyring:
    """Local alias kept so existing tests don't need a wholesale rename."""
    return fake_keyring


@pytest.fixture(autouse=True)
def _isolate_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect ~/.veles to a temp dir so the sidecar index doesn't bleed
    across tests or pollute the real home."""
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "veles"))
    # Clear provider env vars so default fallback doesn't surprise us.
    for env in ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(env, raising=False)


# ---------------- get_provider_key precedence ----------------


def test_scope_wins_over_default(fake_kr: _FakeKeyring) -> None:
    secrets.set_provider_key("openrouter", "default-key")
    secrets.set_provider_key("openrouter", "project-key", project="taxes")
    assert secrets.get_provider_key("openrouter", project="taxes") == "project-key"


def test_default_when_no_scope(fake_kr: _FakeKeyring) -> None:
    secrets.set_provider_key("openrouter", "default-key")
    assert secrets.get_provider_key("openrouter", project="taxes") == "default-key"


def test_env_fallback_when_no_keychain(
    fake_kr: _FakeKeyring, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "env-key")
    assert secrets.get_provider_key("openrouter") == "env-key"


def test_keychain_wins_over_env(fake_kr: _FakeKeyring, monkeypatch: pytest.MonkeyPatch) -> None:
    secrets.set_provider_key("openrouter", "kc-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "env-key")
    assert secrets.get_provider_key("openrouter") == "kc-key"


def test_env_fallback_disabled(fake_kr: _FakeKeyring, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "env-key")
    assert secrets.get_provider_key("openrouter", env_fallback=False) is None


def test_missing_returns_none(fake_kr: _FakeKeyring) -> None:
    assert secrets.get_provider_key("openrouter", project="ghost") is None


# ---------------- list / delete ----------------


def test_list_provider_keys_tracks_scopes(fake_kr: _FakeKeyring) -> None:
    secrets.set_provider_key("openrouter", "k1")
    secrets.set_provider_key("openrouter", "k2", project="taxes")
    secrets.set_provider_key("openrouter", "k3", project="flow")
    assert secrets.list_provider_keys("openrouter") == ["default", "flow", "taxes"]


def test_delete_removes_from_index(fake_kr: _FakeKeyring) -> None:
    secrets.set_provider_key("openrouter", "k1", project="taxes")
    assert secrets.list_provider_keys("openrouter") == ["taxes"]
    assert secrets.delete_provider_key("openrouter", project="taxes")
    assert secrets.list_provider_keys("openrouter") == []
    assert secrets.get_provider_key("openrouter", project="taxes") is None


def test_list_providers_with_keys_snapshot(fake_kr: _FakeKeyring) -> None:
    secrets.set_provider_key("openrouter", "k1", project="a")
    secrets.set_provider_key("anthropic", "k2")
    snap = secrets.list_providers_with_keys()
    assert snap == {"openrouter": ["a"], "anthropic": ["default"]}


def test_empty_value_rejected(fake_kr: _FakeKeyring) -> None:
    with pytest.raises(ValueError):
        secrets.set_provider_key("openrouter", "")


# ---------------- legacy `get_secret` still works ----------------


def test_legacy_get_secret_unaffected(
    fake_kr: _FakeKeyring, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "legacy-env-key")
    assert secrets.get_secret("OPENROUTER_API_KEY") == "legacy-env-key"
    secrets.set_secret("OPENROUTER_API_KEY", "legacy-kc-key")
    assert secrets.get_secret("OPENROUTER_API_KEY") == "legacy-kc-key"
