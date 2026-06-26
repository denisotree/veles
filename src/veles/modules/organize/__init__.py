"""Built-in `organize` module (M175) — layout-driven project tidy-up.

This is a built-in Python module (peer to `modules/wiki/`), NOT core: the
reorg feature, its dispatcher, and the `move_file` primitive all live here so
core stays "memory + learning loop + orchestrator + provider protocol +
minimal tools/skills" (VISION §5.2). The CLI verb (`cli/commands/organize.py`)
is a thin shim that delegates to `run`.
"""

from __future__ import annotations

from veles.modules.organize.orchestrator import run_organize as run

__all__ = ["run"]
