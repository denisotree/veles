"""M100: `validate_and_fetch_models(provider, api_key)` — wizard helper
that proves the key works AND populates the model picker in one shot."""

from __future__ import annotations

import pytest

from veles.tui.screens import _model_fetcher


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
        _model_fetcher, "_try_live", lambda p: ["openai/gpt-4o", "openai/gpt-4o-mini"]
    )
    ok, models, msg = _model_fetcher.validate_and_fetch_models("openai", "sk-key")
    assert ok is True
    assert "openai/gpt-4o" in models
    assert msg == ""


def test_cloud_provider_auth_failure_returns_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_model_fetcher, "_try_live", lambda p: None)
    ok, models, msg = _model_fetcher.validate_and_fetch_models("openrouter", "bad")
    assert ok is False
    assert models == []
    assert "rejected" in msg or "failed" in msg


def test_anthropic_no_list_endpoint_returns_curated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anthropic doesn't expose `/models` to the SDK we use, so the
    fallback returns curated models flagged as "accepted without
    validation" — caller can decide whether to require revalidation."""
    monkeypatch.setattr(
        _model_fetcher,
        "known_models",
        lambda p: ["claude-sonnet-4.6", "claude-haiku-4.5"],
    )
    ok, models, msg = _model_fetcher.validate_and_fetch_models("anthropic", "sk-ant-xxx")
    assert ok is True
    assert "claude-sonnet-4.6" in models
    assert msg == ""


def test_local_provider_uses_live_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_model_fetcher, "_try_live", lambda p: ["llama3", "mistral"])
    ok, models, _msg = _model_fetcher.validate_and_fetch_models("ollama", "ignored")
    assert ok is True
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

    monkeypatch.setattr(_model_fetcher, "_try_live", fake_try_live)
    _model_fetcher.validate_and_fetch_models("openai", "wizard-key")
    import os

    assert seen["during"] == "wizard-key"
    assert os.environ["OPENAI_API_KEY"] == "original-env-key"


def test_env_var_cleared_when_was_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the env was unset before the call, it must remain unset after."""
    import os

    monkeypatch.setattr(_model_fetcher, "_try_live", lambda p: ["m"])
    _model_fetcher.validate_and_fetch_models("openai", "wizard-key")
    assert "OPENAI_API_KEY" not in os.environ
