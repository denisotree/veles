"""M-R1.10: `require_api_key` raises with a consistent message on miss."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from veles.core.provider_factory import make_provider, require_api_key


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


# ---------- local-provider tool-capability auto-detect (replaces VELES_LOCAL_TOOLS gate) ----------

_PROBE = "veles.adapters.local.ollama.OllamaProvider.model_supports_tools"


def test_make_provider_ollama_autodetects_tool_capability(monkeypatch: pytest.MonkeyPatch) -> None:
    """No env flag: tools turn on iff the model advertises the `tools` capability."""
    monkeypatch.delenv("VELES_LOCAL_TOOLS", raising=False)
    monkeypatch.setattr(_PROBE, lambda self, model: model == "qwen3:4b-instruct")
    assert make_provider("ollama", model="qwen3:4b-instruct").supports_tools is True
    assert make_provider("ollama", model="llama2-uncensored").supports_tools is False


def test_make_provider_ollama_no_model_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without a model the capability can't be probed — default off, never probe."""
    monkeypatch.delenv("VELES_LOCAL_TOOLS", raising=False)
    probe = MagicMock(return_value=True)
    monkeypatch.setattr(_PROBE, probe)
    assert make_provider("ollama").supports_tools is False
    probe.assert_not_called()


def test_make_provider_local_tools_env_override_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit VELES_LOCAL_TOOLS forces on/off regardless of model capability."""
    # force ON even though the model has no tool capability (and never probe)
    monkeypatch.setenv("VELES_LOCAL_TOOLS", "1")
    probe = MagicMock(return_value=False)
    monkeypatch.setattr(_PROBE, probe)
    assert make_provider("ollama", model="x").supports_tools is True
    probe.assert_not_called()
    # force OFF even though the model IS tool-capable
    monkeypatch.setenv("VELES_LOCAL_TOOLS", "0")
    monkeypatch.setattr(_PROBE, lambda self, model: True)
    assert make_provider("ollama", model="qwen3:4b-instruct").supports_tools is False
