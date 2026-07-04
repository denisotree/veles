"""REPL-support stack: slash commands, model catalog/fetching, tab
completion, input history, clipboard, and file indexing.

Framework-agnostic — no Textual dependency. The inline REPL
(`cli/commands/repl.py`) is the primary consumer; the (soon to be
removed) Textual chat TUI also imports from here during the M187
transition.
"""

from __future__ import annotations
