import veles.core.tools.builtin  # noqa: F401  (fires registration)
from veles.core.tools.registry import registry


def test_veles_help_registered():
    assert "veles_help" in registry.list_names()


def test_veles_help_returns_full_note_body():
    out = registry.get("veles_help").handler("how do I run an interactive session")
    assert "veles run" in out.lower()


def test_veles_help_handles_no_match():
    out = registry.get("veles_help").handler("zzzz nonexistent qqqq topic")
    assert "no matching veles documentation" in out.lower()
