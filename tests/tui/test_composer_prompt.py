"""ComposerPrompt — inline approval / trust prompt anchored above the
Composer. Drives the widget through a minimal Textual host so the
keybindings, default selection, and future resolution are covered
end-to-end."""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

import pytest
from textual.app import App, ComposeResult
from textual.binding import Binding

from veles.core.trust import TrustChoice
from veles.tui.widgets.composer_prompt import ComposerPrompt, PromptOption


class _Host(App):
    """Minimal host that mounts a single ComposerPrompt for testing.

    Bindings include `up`/`down` because Textual won't deliver them to
    the ListView in `run_test()` if the active screen swallows them
    (and the prompt itself binds them only implicitly via ListView)."""

    BINDINGS: ClassVar[list[Binding]] = []

    def __init__(self, prompt: ComposerPrompt) -> None:
        super().__init__()
        self._prompt = prompt

    def compose(self) -> ComposeResult:
        yield self._prompt


def _make_prompt(
    *,
    loop: asyncio.AbstractEventLoop,
    options: list[PromptOption],
    default_key: Any = None,
    question: str = "Q",
    body: str | None = None,
) -> tuple[ComposerPrompt, asyncio.Future[Any]]:
    future: asyncio.Future[Any] = loop.create_future()
    prompt = ComposerPrompt(
        question=question,
        body=body,
        options=options,
        default_key=default_key,
        future=future,
    )
    return prompt, future


def _trust_options() -> list[PromptOption]:
    return [
        PromptOption(key=TrustChoice.ONCE, label="Once", hotkey="1"),
        PromptOption(key=TrustChoice.ALWAYS_PROJECT, label="Always proj", hotkey="2"),
        PromptOption(key=TrustChoice.ALWAYS_GLOBAL, label="Always global", hotkey="3"),
        PromptOption(key=TrustChoice.REFUSE, label="Refuse", hotkey="4"),
    ]


async def test_hotkey_selects_option_directly() -> None:
    loop = asyncio.get_running_loop()
    prompt, future = _make_prompt(
        loop=loop, options=_trust_options(), default_key=TrustChoice.REFUSE
    )
    app = _Host(prompt)
    async with app.run_test() as pilot:
        await pilot.press("2")
        await pilot.pause()
    assert future.done()
    assert future.result() is TrustChoice.ALWAYS_PROJECT


async def test_enter_on_default_returns_default_key() -> None:
    """The default option must be preselected so a stray Enter returns
    the safe answer."""
    loop = asyncio.get_running_loop()
    prompt, future = _make_prompt(
        loop=loop, options=_trust_options(), default_key=TrustChoice.REFUSE
    )
    app = _Host(prompt)
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
    assert future.result() is TrustChoice.REFUSE


async def test_arrow_navigation_then_enter_picks_highlighted() -> None:
    loop = asyncio.get_running_loop()
    prompt, future = _make_prompt(
        loop=loop, options=_trust_options(), default_key=TrustChoice.REFUSE
    )
    app = _Host(prompt)
    async with app.run_test() as pilot:
        # Default preselected = REFUSE (index 3). One Up → index 2 (ALWAYS_GLOBAL).
        await pilot.press("up")
        await pilot.press("enter")
        await pilot.pause()
    assert future.result() is TrustChoice.ALWAYS_GLOBAL


async def test_escape_returns_default_key_for_approval() -> None:
    loop = asyncio.get_running_loop()
    options = [
        PromptOption(key=True, label="Approve", hotkey="y"),
        PromptOption(key=False, label="Deny", hotkey="n"),
    ]
    prompt, future = _make_prompt(
        loop=loop, options=options, default_key=False, question="Approval?"
    )
    app = _Host(prompt)
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()
    assert future.result() is False


async def test_empty_options_rejected() -> None:
    loop = asyncio.get_running_loop()
    future: asyncio.Future[Any] = loop.create_future()
    with pytest.raises(ValueError):
        ComposerPrompt(
            question="x",
            body=None,
            options=[],
            default_key=None,
            future=future,
        )


# ---- M115.4: freeform-option support ----


async def test_freeform_option_opens_input_then_resolves_with_text() -> None:
    """Universal question-mode (VISION §7.2): when the user picks a
    `freeform=True` option, ComposerPrompt switches to a text input.
    Enter inside the input resolves the future with the typed string
    (wrapped in a `FreeformAnswer` marker so callers can distinguish
    'user picked option N' from 'user typed Y')."""
    from veles.tui.widgets.composer_prompt import FreeformAnswer

    loop = asyncio.get_running_loop()
    options = [
        PromptOption(key="a", label="Variant A", hotkey="1"),
        PromptOption(key="b", label="Variant B", hotkey="2"),
        PromptOption(key="__free__", label="Enter your own answer", hotkey="3", freeform=True),
    ]
    prompt, future = _make_prompt(loop=loop, options=options, default_key="a", question="Pick one")
    app = _Host(prompt)
    async with app.run_test() as pilot:
        await pilot.press("3")
        await pilot.pause()
        # Future is still pending — selection of freeform opens input.
        assert not future.done()
        # Type into the freeform input (Composer's input widget is now mounted).
        for ch in "hello world":
            await pilot.press(ch if ch != " " else "space")
        await pilot.press("enter")
        await pilot.pause()
    assert future.done()
    result = future.result()
    assert isinstance(result, FreeformAnswer)
    assert result.text == "hello world"


async def test_non_freeform_option_still_resolves_immediately() -> None:
    """Adding freeform support must not break the existing flow —
    non-freeform options still resolve right away."""
    loop = asyncio.get_running_loop()
    options = [
        PromptOption(key="a", label="Variant A", hotkey="1"),
        PromptOption(key="__free__", label="Type your own", hotkey="2", freeform=True),
    ]
    prompt, future = _make_prompt(loop=loop, options=options, default_key="a", question="Pick")
    app = _Host(prompt)
    async with app.run_test() as pilot:
        await pilot.press("1")
        await pilot.pause()
    assert future.result() == "a"


async def test_escape_in_freeform_input_returns_default() -> None:
    """Escape in the freeform input cancels back to default — same
    safety property as the top-level prompt."""
    loop = asyncio.get_running_loop()
    options = [
        PromptOption(key="cancel", label="Cancel", hotkey="c"),
        PromptOption(key="__free__", label="Custom", hotkey="f", freeform=True),
    ]
    prompt, future = _make_prompt(loop=loop, options=options, default_key="cancel", question="Pick")
    app = _Host(prompt)
    async with app.run_test() as pilot:
        await pilot.press("f")  # open freeform input
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    assert future.result() == "cancel"
