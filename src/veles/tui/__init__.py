"""Textual surfaces kept after the chat TUI's retirement (M187).

The interactive chat TUI (`app.py`, `bridge.py`, `wire.py`, `widgets/`, the
chat pickers under `screens/`) was deleted in M187 — bare `veles` is now the
prompt_toolkit-based REPL under `veles.cli.repl`. This package now only holds
the surfaces that are still Textual apps in their own right:

- `veles.tui.screens.daemon_picker` — the daemon control panel (`veles daemon`
  with no subcommand).
- `veles.tui.wizard` — the modal-screen wizard framework used by the
  user/project setup wizards.
- `veles.tui.theme_bridge` — theme plumbing shared by the surfaces above.
"""

from __future__ import annotations
