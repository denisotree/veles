"""Tests for core/secrets.py — keychain-backed secret storage (OQ#4 resolved)."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from veles.core.secrets import (
    KeyringUnavailable,
    delete_secret,
    get_secret,
    list_known_names,
    set_secret,
)


def _install_fake_keyring(
    monkeypatch: pytest.MonkeyPatch,
    *,
    store: dict[tuple[str, str], str] | None = None,
    get_raises: BaseException | None = None,
    set_raises: BaseException | None = None,
) -> tuple[MagicMock, dict[tuple[str, str], str]]:
    """Plant a fake `keyring` + `keyring.errors` module in sys.modules.

    Returns the mocked module + the backing store so the test can assert
    on what landed in the keychain.
    """
    s = store if store is not None else {}

    class _PasswordDeleteError(Exception):
        pass

    class _KeyringError(Exception):
        pass

    errors_mod = SimpleNamespace(
        KeyringError=_KeyringError, PasswordDeleteError=_PasswordDeleteError
    )

    def _get_password(service: str, name: str) -> str | None:
        if get_raises is not None:
            raise get_raises
        return s.get((service, name))

    def _set_password(service: str, name: str, value: str) -> None:
        if set_raises is not None:
            raise set_raises
        s[(service, name)] = value

    def _delete_password(service: str, name: str) -> None:
        if (service, name) in s:
            del s[(service, name)]
        else:
            raise _PasswordDeleteError("no such entry")

    keyring_mod = MagicMock()
    keyring_mod.get_password.side_effect = _get_password
    keyring_mod.set_password.side_effect = _set_password
    keyring_mod.delete_password.side_effect = _delete_password
    keyring_mod.errors = errors_mod

    monkeypatch.setitem(sys.modules, "keyring", keyring_mod)
    monkeypatch.setitem(sys.modules, "keyring.errors", errors_mod)
    return keyring_mod, s


# ---------- get_secret ----------


def test_get_secret_keyring_first(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_keyring(monkeypatch, store={("veles", "OPENROUTER_API_KEY"): "from-kc"})
    monkeypatch.setenv("OPENROUTER_API_KEY", "from-env")
    assert get_secret("OPENROUTER_API_KEY") == "from-kc"


def test_get_secret_env_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_keyring(monkeypatch)
    monkeypatch.setenv("MY_TEST_SECRET", "from-env")
    assert get_secret("MY_TEST_SECRET") == "from-env"


def test_get_secret_unset_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_keyring(monkeypatch)
    monkeypatch.delenv("UNSET_SECRET", raising=False)
    assert get_secret("UNSET_SECRET") is None


def test_get_secret_no_env_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_keyring(monkeypatch)
    monkeypatch.setenv("EXISTS_ONLY_IN_ENV", "yes")
    assert get_secret("EXISTS_ONLY_IN_ENV", env_fallback=False) is None


def test_get_secret_when_keyring_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """No `keyring` SDK at all — env fallback still works."""
    monkeypatch.setitem(sys.modules, "keyring", None)
    monkeypatch.setenv("ENV_ONLY", "x")
    assert get_secret("ENV_ONLY") == "x"


def test_get_secret_keyring_error_falls_through(monkeypatch: pytest.MonkeyPatch) -> None:
    """Backend raises (e.g. no daemon on Linux) — env still consulted."""

    class _KErr(Exception):
        pass

    _install_fake_keyring(monkeypatch, get_raises=_KErr("no backend"))
    # Make the KeyringError class match the one our SUT will catch.
    sys.modules["keyring.errors"].KeyringError = _KErr  # type: ignore[attr-defined]
    monkeypatch.setenv("FALLBACK_TEST", "yes")
    assert get_secret("FALLBACK_TEST") == "yes"


# ---------- set_secret ----------


def test_set_secret_stores_under_namespace(monkeypatch: pytest.MonkeyPatch) -> None:
    _, store = _install_fake_keyring(monkeypatch)
    set_secret("ANTHROPIC_API_KEY", "sk-ant-test")
    assert store == {("veles", "ANTHROPIC_API_KEY"): "sk-ant-test"}


def test_set_secret_raises_when_backend_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    class _KErr(Exception):
        pass

    _install_fake_keyring(monkeypatch, set_raises=_KErr("rejected"))
    sys.modules["keyring.errors"].KeyringError = _KErr  # type: ignore[attr-defined]
    with pytest.raises(KeyringUnavailable, match="rejected"):
        set_secret("X", "y")


# ---------- delete_secret ----------


def test_delete_secret_removes_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    _, store = _install_fake_keyring(monkeypatch, store={("veles", "X"): "y"})
    assert delete_secret("X") is True
    assert ("veles", "X") not in store


def test_delete_secret_missing_returns_false(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_keyring(monkeypatch)
    assert delete_secret("MISSING") is False


def test_delete_secret_no_keyring_returns_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "keyring", None)
    assert delete_secret("X") is False


# ---------- list_known_names ----------


def test_list_known_names_includes_canonical_envs() -> None:
    names = list_known_names()
    assert "OPENROUTER_API_KEY" in names
    assert "ANTHROPIC_API_KEY" in names
    assert "OPENAI_API_KEY" in names
    assert "GOOGLE_API_KEY" in names
    assert names == sorted(names)


# ---------- provider_factory wiring ----------


def test_has_api_key_uses_keychain_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """M149: only the scoped naming (`veles:<provider>:<scope>`) is consulted —
    legacy env-named keychain entries (`veles:OPENROUTER_API_KEY`) are ignored."""
    from veles.core.provider_factory import has_api_key

    _install_fake_keyring(monkeypatch, store={("veles", "openrouter:default"): "k"})
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert has_api_key("openrouter") is True


def test_has_api_key_ignores_legacy_env_named_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from veles.core.provider_factory import has_api_key

    _install_fake_keyring(monkeypatch, store={("veles", "OPENROUTER_API_KEY"): "k"})
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert has_api_key("openrouter") is False


def test_has_api_key_falls_back_to_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from veles.core.provider_factory import has_api_key

    _install_fake_keyring(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anything")
    assert has_api_key("anthropic") is True


def test_has_api_key_neither_source_set(monkeypatch: pytest.MonkeyPatch) -> None:
    from veles.core.provider_factory import has_api_key

    _install_fake_keyring(monkeypatch)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert has_api_key("openrouter") is False
