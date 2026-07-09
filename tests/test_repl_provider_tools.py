"""REPL provider construction — native tool-call auto-detection (live 2026-07-08).

`_build_runtime` used to call `_make_provider(args.provider)` WITHOUT the
resolved model, so `provider_factory._apply_local_tool_policy` had nothing to
probe and forced `supports_tools=False` — the inline REPL (the flagship
surface) pushed every local model through the fragile fenced-tools path even
when ollama advertised native tool calling for it. `veles run` and the
curator already passed the model and got native tools.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from tests.conftest import StubProvider
from veles.cli.commands.repl import _build_runtime
from veles.core.context import reset_active_project, set_active_project
from veles.core.layout import clear_engine_cache
from veles.core.project import init_project


@pytest.fixture(autouse=True)
def _fresh_engine_cache():
    clear_engine_cache()
    yield
    clear_engine_cache()


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VELES_USER_HOME", str(tmp_path / "home"))
    p = init_project(tmp_path / "proj", name="proj")
    token = set_active_project(p)
    yield p
    reset_active_project(token)


def _args(**over) -> argparse.Namespace:
    base = dict(
        provider="ollama",
        _provider_explicit=True,  # as if --provider ollama was passed on the CLI
        model="qwen3:4b-instruct",
        resume=None,
        continue_last=False,
        max_iterations=30,
        verbose=False,
        no_agents_md=False,
        no_index=False,
    )
    base.update(over)
    return argparse.Namespace(**base)


def test_build_runtime_passes_model_for_tool_autodetect(project, monkeypatch) -> None:
    seen: dict = {}

    def _fake_make_provider(name, model=None):
        seen["name"] = name
        seen["model"] = model
        return StubProvider(name=name)

    monkeypatch.setattr("veles.cli._make_provider", _fake_make_provider)
    _state, _factory, store, _subf = _build_runtime(_args(), project)
    store.close()
    assert seen["name"] == "ollama"
    assert seen["model"] == "qwen3:4b-instruct"
