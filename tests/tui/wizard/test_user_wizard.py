"""End-to-end coverage of the user-level TUI wizard.

Steps push real ChoiceScreens / InputScreens / ConfirmScreens. We drive
them via Pilot and assert that `WizardApp.run` returns the captured
answers and the API key flow saves to the (mocked) keychain when asked.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# M-R1.8: FakeKeyring centralised in tests/conftest.py.
from tests.conftest import FakeKeyring as _FakeKeyring
from veles.core import secrets
from veles.tui.wizard.app import WizardApp


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _FakeKeyring:
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "veles"))
    for env in ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(env, raising=False)
    kr = _FakeKeyring()
    monkeypatch.setattr(secrets, "_keyring", lambda: (kr, kr.errors))

    # Mock validate_and_fetch_models so the wizard never hits the real
    # network during tests. Always succeed with 2 fake models — tests
    # that need failure paths override this locally.
    from veles.tui.screens import _model_fetcher

    monkeypatch.setattr(
        _model_fetcher,
        "validate_and_fetch_models",
        lambda provider, api_key: (True, [f"{provider}/fake-a", f"{provider}/fake-b"], ""),
    )
    return kr


async def _drive_user_wizard(
    keys: list[str], steps: list | None = None, *, poll: int = 50
) -> dict | None:
    """Mount WizardApp, send each key sequentially with pauses between,
    return the captured answers dict (or None on cancel)."""
    from veles.tui.wizard.user_steps import user_wizard_steps

    app = WizardApp(steps=steps or user_wizard_steps())
    # Override run() to use the Pilot harness. Use App.run_test directly.
    captured = {}

    async with app.run_test() as pilot:
        await pilot.pause()
        for k in keys:
            await pilot.press(k)
            await pilot.pause()
        # Wait briefly for the worker to drive the wizard to completion.
        for _ in range(poll):
            if app.result is not None or app.is_running is False:
                break
            await pilot.pause()
        captured = dict(app.result or {})
    return captured


async def test_local_provider_skips_api_key_step():
    """When the user picks `ollama` we don't ask for an API key — the
    flow jumps straight from provider → theme → init-project."""
    # Keys: language=en (Enter), provider=down*6→ollama (Enter),
    # api-key skipped, theme=enter, init=enter (yes)
    keys = [
        "enter",  # language: en (default)
        # provider: go down to "ollama" from "openrouter" (positions 0..6)
        "down",
        "down",
        "down",
        "down",
        "down",
        "down",
        "enter",  # confirm ollama
        # api key step auto-skips (local provider)
        # model picker: pick default (first model from fake fetch)
        "enter",
        # theme: pick default
        "enter",
        # init project here: Y
        "y",
    ]
    answers = await _drive_user_wizard(keys)
    assert answers["language"] == "en"
    assert answers["default_provider"] == "ollama"
    assert answers["api_key_status"] == "not-required"
    assert answers["default_model"] == "ollama/fake-a"
    assert answers["init_project_here"] is True


async def test_api_key_input_saves_to_keychain():
    """Pick OpenAI → no key found anywhere → InputScreen → type → saved."""
    keys = [
        "enter",  # language en
        # provider: down*2 → openai
        "down",
        "down",
        "enter",  # confirm openai
        # api-key InputScreen — type sk + Enter
        "s",
        "k",
        "-",
        "t",
        "e",
        "s",
        "t",
        "enter",
        # model picker: pick default (first fake model)
        "enter",
        # theme default
        "enter",
        # init project: No
        "n",
    ]
    answers = await _drive_user_wizard(keys)
    assert answers["default_provider"] == "openai"
    assert answers["api_key_status"] == "saved-new"
    assert answers["default_model"] == "openai/fake-a"
    assert answers["init_project_here"] is False
    # Verify the keychain entry exists under the scoped name.
    assert secrets.get_provider_key("openai") == "sk-test"


async def test_existing_keychain_offers_use_or_replace(
    _isolate: _FakeKeyring,
) -> None:
    secrets.set_provider_key("openrouter", "preexisting")
    keys = [
        "enter",  # language en
        "enter",  # provider openrouter (default)
        # ChoiceScreen with [Use existing key, Replace] — pick default (Use)
        "enter",
        "enter",  # model picker default
        "enter",  # theme default
        "n",  # init? no
    ]
    answers = await _drive_user_wizard(keys)
    assert answers["api_key_status"] == "kept-keychain"
    assert secrets.get_provider_key("openrouter") == "preexisting"
    assert answers["default_model"] == "openrouter/fake-a"


async def test_env_value_offers_three_options(
    _isolate: _FakeKeyring, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "env-key")
    keys = [
        "enter",  # language
        "enter",  # provider openrouter
        # Use ENV value (default first option)
        "enter",
        "enter",  # model picker default
        "enter",  # theme
        "n",  # init no
    ]
    answers = await _drive_user_wizard(keys)
    assert answers["api_key_status"] == "env"
    assert answers["default_model"] == "openrouter/fake-a"


async def test_ctrl_q_cancels():
    keys = ["ctrl+q"]
    answers = await _drive_user_wizard(keys)
    assert answers == {}


async def test_model_step_bad_key_continues_with_no(
    _isolate: _FakeKeyring, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When validate_and_fetch_models reports failure, the ModelStep
    offers BACK or continue-without-model. Pressing No → SKIP."""
    from veles.tui.screens import _model_fetcher

    monkeypatch.setattr(
        _model_fetcher,
        "validate_and_fetch_models",
        lambda provider, api_key: (False, [], "401 Unauthorized"),
    )
    secrets.set_provider_key("openrouter", "bad-key")
    keys = [
        "enter",  # language
        "enter",  # provider openrouter
        "enter",  # use existing keychain key
        # ConfirmScreen "go back?" — press n to continue without retry
        "n",
        "enter",  # theme default
        "n",  # init? no
    ]
    answers = await _drive_user_wizard(keys, poll=80)
    assert answers["default_model"] is None
    # api_key_status downgraded to deferred so downstream doesn't trust it.
    assert answers["api_key_status"] == "deferred"
