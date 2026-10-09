"""M325 review fixes: what the first cut of the release got wrong.

- The 0.9·n_ctx ceiling every local Agent now has could drop the newest turn too,
  leaving the system prompt alone: a side call "summarised" nothing and returned a
  fake summary; a headless run answered without its prompt and exited 0.
- A CLI delegate named on the command line became the run base, and a delegate
  can't serve side calls, so the compressor and insights switched off.
- The summariser's input was not bounded by the server it runs on.
- `@t` after `from … import tool as t` was reported as "no @tool function".
"""

from __future__ import annotations

import argparse
from types import SimpleNamespace

from veles.core.context import current_run_base, reset_run_base, set_run_base
from veles.core.context_compressor import emergency_truncate
from veles.core.model_resolver import run_base
from veles.core.project import init_project
from veles.core.provider import Message, ServerFacts
from veles.core.tools.loader import tool_file_problem


def test_emergency_truncation_keeps_the_newest_turn() -> None:
    history = [
        Message(role="system", content="sys"),
        Message(role="user", content="old " * 400),
        Message(role="user", content="the prompt " * 2000),
    ]
    new, dropped = emergency_truncate(history, target_tokens=100)
    assert dropped == 1
    assert new[-1].content.startswith("the prompt")  # still too big: the server says so


def test_a_cli_delegate_is_not_a_run_base(tmp_path) -> None:
    project = init_project(tmp_path / "p", name="p")
    args = argparse.Namespace(provider="claude-cli", model="sonnet", _provider_explicit=True)
    assert run_base(args, project) is None


def test_the_summariser_input_fits_its_server(tmp_path, monkeypatch) -> None:
    import veles.runtime.run as run_mod

    project = init_project(tmp_path / "p", name="p")
    summariser = SimpleNamespace(facts=ServerFacts(reasoning=True, n_ctx=65536))
    seen: dict = {}
    monkeypatch.setattr(run_mod, "make_provider", lambda *a, **k: summariser)
    monkeypatch.setattr(run_mod, "make_default_compressor", lambda **kw: seen.update(kw) or "c")
    token = set_run_base(("llamacpp", "qwen3"))
    try:
        assert run_mod.build_compressor(project, provider=None) == "c"  # type: ignore[arg-type]
    finally:
        reset_run_base(token)
    assert seen["cfg"].max_summariser_input_tokens == 32768


def test_an_aliased_tool_decorator_counts() -> None:
    src = (
        "from veles.core.tools.registry import tool as t\n\n@t()\ndef f() -> str:\n    return ''\n"
    )
    assert tool_file_problem(src) is None


def test_a_repl_model_switch_moves_the_run_base() -> None:
    from veles.cli.repl.turn import _follow_model_switch

    token = set_run_base(("ollama", "qwen3:4b"))
    try:
        _follow_model_switch("llama3.2")
        assert current_run_base() == ("ollama", "llama3.2")
    finally:
        reset_run_base(token)


def test_no_run_base_stays_none_on_a_model_switch() -> None:
    from veles.cli.repl.turn import _follow_model_switch

    _follow_model_switch("llama3.2")
    assert current_run_base() is None
