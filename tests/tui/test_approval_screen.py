"""ApprovalScreen + TrustScreen modal dismissal behaviour.

We host each screen in a minimal App and read the dismissed value
through the standard `push_screen + callback` pattern. The bridge's
`call_from_thread + push_screen_wait` path is exercised indirectly by
`test_bridge_prompters.py`.
"""

from __future__ import annotations

from textual.app import App, ComposeResult

from veles.core.trust import TrustChoice
from veles.tui.screens.approval_screen import ApprovalScreen, TrustScreen


class _ModalHost(App):
    def __init__(self, screen) -> None:
        super().__init__()
        self._screen = screen
        self.picked: object = "SENTINEL"

    def on_mount(self) -> None:
        def _on_dismiss(value):
            self.picked = value

        self.push_screen(self._screen, _on_dismiss)

    def compose(self) -> ComposeResult:
        return iter(())


# ---------------- ApprovalScreen ----------------


async def test_approval_y_returns_true():
    app = _ModalHost(ApprovalScreen("run_shell", {"cmd": "ls"}, "external write"))
    async with app.run_test() as pilot:
        await pilot.press("y")
        await pilot.pause()
    assert app.picked is True


async def test_approval_uppercase_y_returns_true():
    app = _ModalHost(ApprovalScreen("run_shell", {}, ""))
    async with app.run_test() as pilot:
        await pilot.press("Y")
        await pilot.pause()
    assert app.picked is True


async def test_approval_n_returns_false():
    app = _ModalHost(ApprovalScreen("run_shell", {}, ""))
    async with app.run_test() as pilot:
        await pilot.press("n")
        await pilot.pause()
    assert app.picked is False


async def test_approval_escape_denies():
    app = _ModalHost(ApprovalScreen("run_shell", {}, ""))
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()
    assert app.picked is False


async def test_approval_enter_defaults_to_deny():
    """`[y/N]` convention: a bare Enter must not approve a sensitive op."""
    app = _ModalHost(ApprovalScreen("run_shell", {}, ""))
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
    assert app.picked is False


# ---------------- TrustScreen ----------------


async def test_trust_1_returns_once():
    app = _ModalHost(TrustScreen("run_shell"))
    async with app.run_test() as pilot:
        await pilot.press("1")
        await pilot.pause()
    assert app.picked == TrustChoice.ONCE


async def test_trust_2_returns_always_project():
    app = _ModalHost(TrustScreen("run_shell"))
    async with app.run_test() as pilot:
        await pilot.press("2")
        await pilot.pause()
    assert app.picked == TrustChoice.ALWAYS_PROJECT


async def test_trust_3_returns_always_global():
    app = _ModalHost(TrustScreen("run_shell"))
    async with app.run_test() as pilot:
        await pilot.press("3")
        await pilot.pause()
    assert app.picked == TrustChoice.ALWAYS_GLOBAL


async def test_trust_4_returns_refuse():
    app = _ModalHost(TrustScreen("run_shell"))
    async with app.run_test() as pilot:
        await pilot.press("4")
        await pilot.pause()
    assert app.picked == TrustChoice.REFUSE


async def test_trust_escape_refuses():
    app = _ModalHost(TrustScreen("run_shell"))
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()
    assert app.picked == TrustChoice.REFUSE


async def test_trust_enter_refuses():
    app = _ModalHost(TrustScreen("run_shell"))
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
    assert app.picked == TrustChoice.REFUSE
