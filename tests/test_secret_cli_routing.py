"""M271: `veles secret` manages provider keys where the runtime reads them.

There were two keychain layouts and the command only knew one. The setup wizard
stores a provider key at `veles:<provider>:<scope>` (M92) and that is the only
place `provider_factory.resolve_api_key` looks — M149 deliberately stopped
reading the flat `veles:OPENROUTER_API_KEY` form. `veles secret` kept writing
exactly that flat form. Measured before the fix, with an in-memory keyring:

  - `veles secret set OPENROUTER_API_KEY` → stored, and the provider saw no key;
  - a key stored by the wizard → working, and `veles secret list` said "(unset)".

Every test drives the real CLI entry (`veles.cli.main`) and then asks the
runtime resolver, because the bug was precisely that the command and the
runtime disagreed — a test of either side alone passed.
"""

from __future__ import annotations

import pytest

from veles.cli import main as cli_main
from veles.core.provider_factory import resolve_api_key
from veles.core.secrets import provider_for_env_name, set_provider_key


@pytest.fixture(autouse=True)
def _no_env_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "OPENROUTER_API_KEY",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "TAVILY_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


def test_provider_names_route_to_their_provider() -> None:
    assert provider_for_env_name("OPENROUTER_API_KEY") == "openrouter"
    assert provider_for_env_name("GOOGLE_API_KEY") == "gemini"
    assert provider_for_env_name("GEMINI_API_KEY") == "gemini"
    assert provider_for_env_name("TAVILY_API_KEY") is None


def test_set_reaches_the_provider(fake_keyring) -> None:
    """The reported bug, end to end: this returned False before M271."""
    assert cli_main(["secret", "set", "OPENROUTER_API_KEY", "sk-test"]) == 0
    assert resolve_api_key("openrouter") == "sk-test"
    # And the flat legacy entry the runtime ignores was NOT written.
    assert ("veles", "OPENROUTER_API_KEY") not in fake_keyring.store


def test_set_with_project_scopes_the_key(fake_keyring) -> None:
    assert cli_main(["secret", "set", "OPENROUTER_API_KEY", "sk-proj", "--project", "p"]) == 0
    assert fake_keyring.store[("veles", "openrouter:p")] == "sk-proj"
    assert ("veles", "openrouter:default") not in fake_keyring.store


def test_delete_removes_a_key_the_wizard_stored(fake_keyring) -> None:
    """A wizard-stored key could not be revoked from the CLI at all before."""
    set_provider_key("openrouter", "sk-wizard")  # exactly what the wizard calls
    assert cli_main(["secret", "delete", "OPENROUTER_API_KEY"]) == 0
    assert resolve_api_key("openrouter") is None


def test_get_sees_a_key_the_wizard_stored(fake_keyring, capsys) -> None:
    set_provider_key("openrouter", "sk-wizard")
    assert cli_main(["secret", "get", "OPENROUTER_API_KEY"]) == 0
    assert "is set" in capsys.readouterr().err


def test_empty_provider_key_is_refused_not_stored(fake_keyring, capsys) -> None:
    assert cli_main(["secret", "set", "OPENROUTER_API_KEY", ""]) == 2
    assert "empty" in capsys.readouterr().err
    assert resolve_api_key("openrouter") is None


def test_project_flag_is_rejected_for_a_plain_secret(fake_keyring, capsys) -> None:
    """Silently ignoring `--project` would store a global secret the user
    believed was scoped — say so instead."""
    assert cli_main(["secret", "set", "TAVILY_API_KEY", "t", "--project", "p"]) == 2
    assert "provider API keys only" in capsys.readouterr().err
    assert fake_keyring.store == {}


# ---- list ----


def _listed(capsys, name: str) -> str:
    for line in capsys.readouterr().out.splitlines():
        if line.split() and line.split()[0] == name:
            return line.split(None, 1)[1].strip()
    raise AssertionError(f"{name} not listed")


def test_list_shows_a_wizard_stored_key(fake_keyring, capsys) -> None:
    """The other half of the reported bug: this printed "(unset)"."""
    set_provider_key("openrouter", "sk-wizard")
    set_provider_key("openrouter", "sk-proj", project="myproj")
    assert cli_main(["secret", "list"]) == 0
    assert _listed(capsys, "OPENROUTER_API_KEY") == "keychain (default, myproj)"


def test_list_does_not_trust_a_stale_index(fake_keyring, capsys) -> None:
    """The sidecar index can outlive an entry revoked outside Veles; reporting
    a key that is gone would be the mirror image of the bug."""
    set_provider_key("openrouter", "sk-wizard")
    fake_keyring.store.clear()  # revoked in the OS keychain UI
    assert cli_main(["secret", "list"]) == 0
    assert _listed(capsys, "OPENROUTER_API_KEY") == "(unset)"


def test_list_names_env_alongside_keychain(fake_keyring, capsys, monkeypatch) -> None:
    set_provider_key("anthropic", "k")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "also-in-env")
    assert cli_main(["secret", "list"]) == 0
    assert _listed(capsys, "ANTHROPIC_API_KEY") == "keychain (default); env"


def test_list_shows_channel_credentials(fake_keyring, capsys) -> None:
    set_provider_key("telegram", "bot-token", project="myproj")  # channel_wizard's call
    assert cli_main(["secret", "list"]) == 0
    out = capsys.readouterr().out
    assert "channel credentials:" in out
    assert "telegram" in out and "keychain (myproj)" in out


def test_plain_secrets_keep_their_flat_entry(fake_keyring) -> None:
    assert cli_main(["secret", "set", "TAVILY_API_KEY", "tv-key"]) == 0
    assert fake_keyring.store[("veles", "TAVILY_API_KEY")] == "tv-key"
