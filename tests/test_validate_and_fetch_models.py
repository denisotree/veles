"""M100: `validate_and_fetch_models(provider, api_key)` — wizard helper
that proves the key works AND populates the model picker in one shot."""

from __future__ import annotations

import pytest

from veles.cli.repl import model_fetcher


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for env in (
        "OPENROUTER_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
    ):
        monkeypatch.delenv(env, raising=False)


def test_cloud_provider_success_returns_live_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        model_fetcher, "_list_live", lambda p: ["openai/gpt-4o", "openai/gpt-4o-mini"]
    )
    status, models, msg = model_fetcher.validate_and_fetch_models("openai", "sk-key")
    assert status == "ok"
    assert "openai/gpt-4o" in models
    assert msg == ""


def test_cloud_provider_auth_failure_returns_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(model_fetcher, "_list_live", lambda p: None)
    status, models, msg = model_fetcher.validate_and_fetch_models("openrouter", "bad")
    assert status == "rejected"
    assert models == []
    assert "rejected" in msg or "failed" in msg


def test_a_provider_that_never_answers_is_unreachable_not_a_freeze(monkeypatch) -> None:
    """A closed network: the SDKs wait minutes with retries, and the wizard froze."""
    import time

    monkeypatch.setattr(model_fetcher, "FETCH_TIMEOUT_S", 0.2)
    monkeypatch.setattr(model_fetcher, "_list_live", lambda p: time.sleep(5) or ["x"])
    started = time.monotonic()
    status, models, msg = model_fetcher.validate_and_fetch_models("openrouter", "sk")
    assert status == "unreachable" and models == [] and "0s" in msg
    assert time.monotonic() - started < 2


def test_a_network_error_is_unreachable_and_401_is_rejected(monkeypatch) -> None:
    class _Auth(Exception):
        status_code = 401

    def boom(exc):
        def _live(p):
            raise exc

        return _live

    monkeypatch.setattr(model_fetcher, "_list_live", boom(ConnectionError("no route")))
    assert model_fetcher.validate_and_fetch_models("openrouter", "sk")[0] == "unreachable"
    monkeypatch.setattr(model_fetcher, "_list_live", boom(_Auth("bad key")))
    assert model_fetcher.validate_and_fetch_models("openrouter", "sk")[0] == "rejected"


def test_anthropic_no_list_endpoint_returns_curated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anthropic doesn't expose `/models` to the SDK we use, so the
    fallback returns curated models flagged as "accepted without
    validation" — caller can decide whether to require revalidation."""
    monkeypatch.setattr(
        model_fetcher,
        "known_models",
        lambda p: ["claude-sonnet-4.6", "claude-haiku-4.5"],
    )
    status, models, msg = model_fetcher.validate_and_fetch_models("anthropic", "sk-ant-xxx")
    assert status == "ok"
    assert "claude-sonnet-4.6" in models
    assert msg == ""


def test_local_provider_uses_live_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(model_fetcher, "_list_live", lambda p: ["llama3", "mistral"])
    status, models, _msg = model_fetcher.validate_and_fetch_models("ollama", "ignored")
    assert status == "ok"
    assert "llama3" in models


def test_env_var_is_restored_after_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "original-env-key")
    seen: dict[str, str] = {}

    def fake_try_live(provider: str) -> list[str]:
        import os

        seen["during"] = os.environ.get("OPENAI_API_KEY", "")
        return ["model"]

    monkeypatch.setattr(model_fetcher, "_list_live", fake_try_live)
    model_fetcher.validate_and_fetch_models("openai", "wizard-key")
    import os

    assert seen["during"] == "wizard-key"
    assert os.environ["OPENAI_API_KEY"] == "original-env-key"


def test_env_var_cleared_when_was_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the env was unset before the call, it must remain unset after."""
    import os

    monkeypatch.setattr(model_fetcher, "_list_live", lambda p: ["m"])
    model_fetcher.validate_and_fetch_models("openai", "wizard-key")
    assert "OPENAI_API_KEY" not in os.environ
