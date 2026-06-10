"""M-R1.10: `require_api_key` raises with a consistent message on miss."""

from __future__ import annotations

import pytest

from veles.core.provider_factory import require_api_key


def test_returns_explicit_key() -> None:
    assert require_api_key("openrouter", explicit="sk-test") == "sk-test"


def test_raises_when_nothing_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    for env in ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setattr(
        "veles.core.provider_factory.resolve_api_key", lambda name, *, explicit=None: None
    )
    with pytest.raises(RuntimeError, match="openrouter"):
        require_api_key("openrouter")


def test_error_message_mentions_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """Users glance at the message to know which env var to set."""
    monkeypatch.setattr(
        "veles.core.provider_factory.resolve_api_key", lambda name, *, explicit=None: None
    )
    with pytest.raises(RuntimeError) as excinfo:
        require_api_key("openrouter")
    assert "$OPENROUTER_API_KEY" in str(excinfo.value)


def test_error_message_for_unknown_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unknown provider — no env hint available, but error still fires."""
    monkeypatch.setattr(
        "veles.core.provider_factory.resolve_api_key", lambda name, *, explicit=None: None
    )
    with pytest.raises(RuntimeError, match="not-a-provider"):
        require_api_key("not-a-provider")
