"""M-R1.10: `require_api_key` raises with a consistent message on miss."""

from __future__ import annotations

import pytest

from veles.core.provider import ServerFacts
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

_PROBE = "veles.adapters.local.ollama.OllamaProvider.server_facts"


def _tools_if(capable: bool) -> ServerFacts:
    return ServerFacts(tools=capable)


def test_make_provider_ollama_autodetects_tool_capability(monkeypatch: pytest.MonkeyPatch) -> None:
    """No env flag: tools turn on iff the model advertises the `tools` capability."""
    monkeypatch.delenv("VELES_LOCAL_TOOLS", raising=False)
    monkeypatch.setattr(_PROBE, lambda self, model: _tools_if(model == "qwen3:4b-instruct"))
    assert make_provider("ollama", model="qwen3:4b-instruct").supports_tools is True
    assert make_provider("ollama", model="llama2-uncensored").supports_tools is False


def test_make_provider_ollama_no_model_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without a model ollama cannot answer, and says so itself.

    M256 moved that decision out of the factory and into the probe. The factory
    used to refuse to ask when it had no model name — correct while ollama was
    the only backend, since its question is "does THIS model support tools". But
    llama.cpp serves one model chosen at startup and answers for itself, so the
    blanket refusal left it tool-blind. Ollama's own `not model` guard keeps this
    case off, and does it without a request."""
    monkeypatch.delenv("VELES_LOCAL_TOOLS", raising=False)
    calls: list[str] = []
    monkeypatch.setattr("httpx.post", lambda *a, **kw: calls.append("posted"))
    assert make_provider("ollama").supports_tools is False
    assert calls == []  # guarded before any HTTP


def test_make_provider_local_tools_env_override_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit VELES_LOCAL_TOOLS forces on/off regardless of model capability.

    The server is still asked (M325): the same answer sets the completion cap
    and the context ceiling, which the override says nothing about."""
    # force ON even though the model has no tool capability
    monkeypatch.setenv("VELES_LOCAL_TOOLS", "1")
    monkeypatch.setattr(_PROBE, lambda self, model: _tools_if(False))
    assert make_provider("ollama", model="x").supports_tools is True
    # force OFF even though the model IS tool-capable
    monkeypatch.setenv("VELES_LOCAL_TOOLS", "0")
    monkeypatch.setattr(_PROBE, lambda self, model: _tools_if(True))
    assert make_provider("ollama", model="qwen3:4b-instruct").supports_tools is False


def test_gemini_cli_is_retired_with_a_hint() -> None:
    with pytest.raises(ValueError, match=r"removed in 1\.2\.6") as exc:
        make_provider("gemini-cli")
    assert "GEMINI_API_KEY" in str(exc.value) and "antigravity-cli" in str(exc.value)
