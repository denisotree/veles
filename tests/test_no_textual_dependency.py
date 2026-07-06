"""Invariant: Veles carries no Textual dependency (M197).

The chat TUI was retired (M187) and the daemon picker + wizards were moved
onto prompt_toolkit / stdin (M197). Guard both facets so the dependency
can't creep back: no `import textual` in the source tree, and the old
`veles.tui` package is unimportable.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parent.parent / "src" / "veles"
_TEXTUAL_RE = re.compile(r"^\s*(?:import\s+textual|from\s+textual)\b", re.MULTILINE)


def test_no_textual_imports_in_source() -> None:
    offenders: list[str] = []
    for path in _SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if _TEXTUAL_RE.search(text):
            offenders.append(str(path.relative_to(_SRC.parent.parent)))
    assert not offenders, "Textual imports leaked back into src/veles:\n  " + "\n  ".join(offenders)


def test_veles_tui_package_is_gone() -> None:
    with pytest.raises(ModuleNotFoundError):
        __import__("veles.tui")


def test_textual_not_a_declared_dependency() -> None:
    pyproject = (_SRC.parent.parent / "pyproject.toml").read_text(encoding="utf-8")
    # Naive but sufficient: the dep list would carry a `"textual...` entry.
    assert '"textual' not in pyproject
