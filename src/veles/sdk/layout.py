"""Layout packs, the project context file, and subprojects."""

from __future__ import annotations

from veles.core.layout.discovery import find_layout
from veles.core.layout.manifest import LayoutManifest
from veles.core.subproject import load_subprojects, resolve_subproject_path
from veles.runtime.prompt import load_context_file

__all__ = [
    "LayoutManifest",
    "find_layout",
    "load_context_file",
    "load_subprojects",
    "resolve_subproject_path",
]
