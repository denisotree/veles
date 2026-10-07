"""The project wizard's model step in a closed network: a typed model id instead of
an empty picker (1.2.10)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from veles.core.project import init_project


class _App:
    def __init__(self, answer: object) -> None:
        self.answer = answer
        self.screens: list[object] = []

    async def push_screen_wait(self, screen: object) -> object:
        self.screens.append(screen)
        return self.answer


async def test_an_unreachable_provider_asks_for_a_model_id(tmp_path, monkeypatch) -> None:
    from veles.cli.repl import model_fetcher
    from veles.tui.wizard import project_steps
    from veles.tui.wizard.screens import InputScreen

    monkeypatch.setattr(
        model_fetcher,
        "validate_and_fetch_models",
        lambda provider, key: ("unreachable", [], "ollama didn't answer in 10s"),
    )
    monkeypatch.setattr(model_fetcher, "known_models", lambda provider: [])
    app = _App("qwen3:4b")
    ctx = SimpleNamespace(app=app, answers={"project": init_project(tmp_path / "p", name="p")})
    picked = await project_steps._pick_project_model(ctx, "ollama", default_pref=None)
    assert picked == "qwen3:4b"
    assert isinstance(app.screens[0], InputScreen)


@pytest.mark.parametrize("answer", ["", None])
async def test_no_typed_model_means_none(tmp_path, monkeypatch, answer) -> None:
    from veles.cli.repl import model_fetcher
    from veles.tui.wizard import project_steps

    monkeypatch.setattr(
        model_fetcher,
        "validate_and_fetch_models",
        lambda provider, key: ("unreachable", [], "x"),
    )
    monkeypatch.setattr(model_fetcher, "known_models", lambda provider: [])
    ctx = SimpleNamespace(
        app=_App(answer), answers={"project": init_project(tmp_path / "p", name="p")}
    )
    assert await project_steps._pick_project_model(ctx, "ollama", default_pref=None) is None
