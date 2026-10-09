import veles.core.tools.builtin  # noqa: F401  (fires registration)
from veles.core.tools.registry import registry


def test_veles_help_registered():
    assert "veles_help" in registry.list_names()


def test_veles_help_returns_full_note_body():
    out = registry.get("veles_help").handler("how do I run an interactive session")
    assert "veles run" in out.lower()


def _titles(out: str) -> list[str]:
    return [line[3:] for line in out.splitlines() if line.startswith("## ")]


def test_veles_help_finds_the_tool_contract_for_the_reported_queries():
    """M325: the three queries Qwen3.8 actually sent (events.jsonl of the run)
    got the trust note, the trust note again, and nothing — so the model gave up
    and wrote an argparse script instead of a tool."""
    handler = registry.get("veles_help").handler
    for q in (
        "how to create a custom reusable python tool in .veles/tools, "
        "expected file format and function signature",
        "custom tools project tools directory tool_authoring python tool signature",
        "veles tool list python tool file format main function arguments",
    ):
        assert _titles(handler(q))[0] == "Author a Veles tool", q


def test_veles_help_finds_a_one_word_name():
    """A skill/tool/command name is one token, and recall's two-token gate made
    every one of them unreachable (60 of 153 entries)."""
    handler = registry.get("veles_help").handler
    assert "tool_authoring" in _titles(handler("tool_authoring"))


def test_the_tool_note_stays_out_of_coding_recall():
    """The gate `veles_help` relaxes is the one that keeps Veles docs out of an
    ordinary coding prompt — recall must still refuse these."""
    from veles.core.knowledge.store import get_default_store

    store = get_default_store()
    for q in (
        "write a python function that reads a file",
        "add a tool to parse json in python",
        "write a custom tool for parsing logs",
        "fix the bug in read_file",
    ):
        assert store.search(q) == [], q


def test_plural_and_singular_are_one_match():
    """`tool` + `tools` used to count twice and clear the gate on their own."""
    from veles.core.knowledge.store import _tokens

    assert _tokens("tools tool") == {"tool"}
    assert _tokens("uses") == set()  # singularised into a stopword


def test_veles_help_handles_no_match():
    out = registry.get("veles_help").handler("zzzz nonexistent qqqq topic")
    assert "no matching veles documentation" in out.lower()
