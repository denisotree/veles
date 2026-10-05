"""Installing a registry pick from a Textual wizard: the confirmation is a
terminal prompt, so the app hands the terminal back while it runs."""

from __future__ import annotations

import sys
from collections.abc import Callable

from textual.app import App


def install_with_terminal(app: App, install: Callable[[], bool], *, hint: str) -> bool:
    from textual.app import SuspendNotSupported

    try:
        with app.suspend():
            return install()
    except SuspendNotSupported:
        print(f"can't install here — {hint}", file=sys.stderr)
        return False
