"""Writing agent tools: the `@tool` decorator, risk classes, path and write guards,
and the builtin tools a module may call directly."""

from __future__ import annotations

from veles.core.agent_state import current_toolset
from veles.core.path_guard import is_inside, resolve_safe
from veles.core.risk import RiskClass
from veles.core.safety import scan_for_injection
from veles.core.tools.builtin.fetch_url import fetch_url
from veles.core.tools.builtin.fs_write_guard import guard_write
from veles.core.tools.builtin.read_file import read_file
from veles.core.tools.registry import tool
from veles.core.tools.toolsets import TOOLSETS
from veles.core.untrusted import trust_frontmatter

__all__ = [
    "TOOLSETS",
    "RiskClass",
    "current_toolset",
    "fetch_url",
    "guard_write",
    "is_inside",
    "read_file",
    "resolve_safe",
    "scan_for_injection",
    "tool",
    "trust_frontmatter",
]
