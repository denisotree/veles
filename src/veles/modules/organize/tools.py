"""Re-export of the generic `move_file` primitive.

`move_file` was relocated to `core/tools/builtin/file_ops.py` so it is ALWAYS
registered and usable from the interactive `[run]` toolset — not only when the
organize dispatcher imports this module. It is kept re-exported here so existing
imports of `veles.modules.organize.tools` (and the orchestrator's side-effect
import) still resolve; the actual `@tool` registration now lives in builtin, so
importing this module no longer double-registers.
"""

from __future__ import annotations

from veles.core.tools.builtin.file_ops import move_file

__all__ = ["move_file"]
