"""The Textual channel flow lists registry platforms and installs a pick with the
terminal handed back (`App.suspend`), like the layout picker."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest


@dataclass
class _StubApp:
    responses: list[Any] = field(default_factory=list)
    pushed: list[Any] = field(default_factory=list)
    suspended: int = 0

    async def push_screen_wait(self, screen: Any) -> Any:
        self.pushed.append(screen)
        if not self.responses:
            raise AssertionError("test queued no response for push_screen_wait")
        return self.responses.pop(0)

    @contextlib.contextmanager
    def suspend(self) -> Iterator[None]:
        self.suspended += 1
        yield


async def test_registry_platform_is_listed_and_installed_with_the_terminal(
    monkeypatch: pytest.MonkeyPatch, fake_platform
) -> None:
    from veles.core.registry import ensure
    from veles.tui.wizard.channel_flow import collect_channel_via_modals

    monkeypatch.setattr(ensure, "available_platforms", lambda: ["fake", "slackish"])
    asked: list[str] = []
    monkeypatch.setattr(
        ensure, "ensure_platform_interactive", lambda name: asked.append(name) or False
    )
    app = _StubApp(responses=["slackish"])
    assert await collect_channel_via_modals(app, title="Add channel") is None  # declined
    labels = [item.label for item in app.pushed[0]._items]
    assert any("slackish" in x and "registry" in x for x in labels), labels
    assert any(x == "fake" for x in labels)
    assert asked == ["slackish"] and app.suspended == 1
