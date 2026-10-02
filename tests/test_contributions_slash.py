"""`slash_command` — a module adds a REPL command; builtin names stay builtin, and
an engine-bound command shows only where its engine is on."""

from __future__ import annotations

from pathlib import Path

import pytest

from veles.core.contributions import SlashCommand, SlashReply
from veles.core.modules import ModuleAPI, ModuleRegistry, reset_module_registry, set_module_registry
from veles.core.project import init_project


@pytest.fixture()
def bare(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    return init_project(tmp_path / "b", name="b", layout="bare")


def _with(**commands: SlashCommand):
    scratch, reg = ModuleRegistry(), ModuleRegistry()
    api = ModuleAPI(scratch, "m")
    for name, cmd in commands.items():
        api.contribute("slash_command", name, cmd)
    reg.merge_from(scratch, "m")
    return set_module_registry(reg)


def _ctx(project):
    from veles.cli.repl.slash.registry import SlashContext
    from veles.core.memory import SessionStore
    from veles.core.session_state import AppState

    state = AppState(session_id=None, provider_name="stub", model="m")
    return SlashContext(state=state, project=project, store=SessionStore(project.memory_db_path))


def test_module_slash_command_dispatches(bare) -> None:
    from veles.cli.repl.slash import build_default_registry

    seen: list[str] = []

    def run(project, arg: str) -> SlashReply:
        seen.append(arg)
        return SlashReply(text="pinged", submit_prompt=f"say {arg}")

    token = _with(ping=SlashCommand(run=run, summary="ping the agent", usage="/ping <x>"))
    try:
        reg = build_default_registry(bare)
        res = reg.dispatch("/ping hello", _ctx(bare))
        help_text = reg.dispatch("/help", _ctx(bare))
    finally:
        reset_module_registry(token)
    assert seen == ["hello"]
    assert res is not None and res.text == "pinged" and res.submit_prompt == "say hello"
    assert help_text is not None and "ping the agent" in help_text.text


def test_error_reply_is_an_error(bare) -> None:
    from veles.cli.repl.slash import build_default_registry

    token = _with(bad=SlashCommand(run=lambda p, a: SlashReply(text="nope", error=True)))
    try:
        res = build_default_registry(bare).dispatch("/bad", _ctx(bare))
    finally:
        reset_module_registry(token)
    assert res is not None and res.is_error and res.text == "nope"


def test_engine_bound_command_hidden_when_engine_off(bare) -> None:
    from veles.cli.repl.slash import build_default_registry

    token = _with(
        gated=SlashCommand(run=lambda p, a: SlashReply(text="x"), engine="not-enabled-here")
    )
    try:
        names = build_default_registry(bare).names()
    finally:
        reset_module_registry(token)
    assert "/gated" not in names


def test_builtin_name_cannot_be_taken(bare, capsys) -> None:
    from veles.cli.repl.slash import build_default_registry

    token = _with(help=SlashCommand(run=lambda p, a: SlashReply(text="hijacked")))
    try:
        res = build_default_registry(bare).dispatch("/help", _ctx(bare))
    finally:
        reset_module_registry(token)
    assert res is not None and res.text != "hijacked"
    assert "/help" in capsys.readouterr().err
