"""Release E: a provider contributed by an installed user module works where a
builtin does — the flag, veles models, has_api_key."""

from __future__ import annotations

import argparse
from pathlib import Path

from veles.core.provider import Message
from veles.core.registry.gate import approve_module
from veles.core.user_paths import user_modules_dir

_MODULE = """
from veles.sdk.providers import ProviderResponse, ProviderSpec, TokenUsage


class EchoProvider:
    name = "echo"
    supports_tools = False
    supports_streaming = False

    def create_message(self, messages, tools=None, *, model, max_tokens=4096):
        text = messages[-1].content or ""
        return ProviderResponse(text=f"echo: {text}", tool_calls=[], usage=TokenUsage())

    def list_models(self):
        return ["echo-1"]


SPEC = ProviderSpec(label="Echo", build=lambda ctx: EchoProvider(), model_list="live")


def register(api):
    api.contribute("provider", "echo", SPEC)
"""


def _install_echo() -> None:
    mod = user_modules_dir() / "echo"
    mod.mkdir(parents=True)
    (mod / "module.toml").write_text(
        '[module]\nname = "echo"\ndescription = "d"\nentrypoint = "e.py:register"\n',
        encoding="utf-8",
    )
    (mod / "e.py").write_text(_MODULE, encoding="utf-8")
    approve_module(mod, name="echo", project_root=None)


def test_a_module_provider_through_the_cli(isolated_user_home: Path, capsys) -> None:
    from veles.cli._console import ensure_api_key
    from veles.cli.commands.models import cmd_models
    from veles.core.provider_factory import make_provider

    _install_echo()
    assert ensure_api_key("echo") is True
    assert cmd_models(argparse.Namespace(provider="echo", refresh=False, as_json=False)) == 0
    assert "echo-1" in capsys.readouterr().out
    reply = make_provider("echo").create_message([Message(role="user", content="hi")], model="e")
    assert reply.text == "echo: hi"
