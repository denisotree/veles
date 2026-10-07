"""The wizard-facing helpers of the provider catalogue."""

from __future__ import annotations

from veles.core.providers import list_providers, tui_label


def test_tui_label_includes_tagline_when_present() -> None:
    assert tui_label("ollama") == "Ollama (local, no key)"


def test_tui_label_omits_empty_tagline() -> None:
    assert tui_label("gemini") == "Google Gemini"


def test_default_order_openrouter_first() -> None:
    assert list_providers()[0] == "openrouter"
