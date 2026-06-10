"""Tool registry and builtin tools.

Importing this package triggers `@tool` registration for all builtins.
"""

from veles.core.tools import builtin as _builtin  # noqa: F401  -- side-effect import
from veles.core.tools.registry import Registry, ToolEntry, registry, tool

__all__ = ["Registry", "ToolEntry", "registry", "tool"]
