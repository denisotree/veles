"""Regression guard: internal milestone numbers (M77, M92, ...) must
not leak into user-facing strings.

What counts as user-facing here:
  - argparse `help=` text in `cli/_parsers/*.py` (printed by `--help`)
  - i18n locale files in `src/veles/locales/*.toml`
  - Label / Static widget text and `print(...)` calls in wizard screens

We deliberately do NOT scan docstrings or `#` comments — those serve
developer documentation. The scanner uses an AST walk so it ignores
both. The whole `MILESTONES.md`, `CLAUDE.md`, etc. are also excluded
because they are dev-facing changelogs.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_M_NUMBER_RE = re.compile(r"\bM\d{2,}\b")


def _user_facing_string_literals(path: Path) -> list[tuple[int, str]]:
    """Return (lineno, value) for every str literal in `path` that is
    NOT a docstring. Docstrings are filtered by AST: the first
    `Expr(Constant(str))` of a module / class / function body."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    # Collect docstring nodes to skip.
    skip_ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                skip_ids.add(id(body[0].value))
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in skip_ids:
                continue
            out.append((node.lineno, node.value))
    return out


def _scan_python(path: Path) -> list[tuple[int, str]]:
    """Return (line, leaked-snippet) tuples for user-facing string
    literals in `path` that contain an internal milestone reference."""
    bad: list[tuple[int, str]] = []
    for lineno, literal in _user_facing_string_literals(path):
        if _M_NUMBER_RE.search(literal):
            bad.append((lineno, literal))
    return bad


def _scan_toml(path: Path) -> list[tuple[int, str]]:
    bad: list[tuple[int, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    for i, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("#"):
            continue
        if _M_NUMBER_RE.search(line):
            bad.append((i, line.rstrip()))
    return bad


@pytest.mark.parametrize(
    "rel_path",
    [
        "src/veles/cli/_parsers",
        "src/veles/tui/wizard",
        "src/veles/tui/screens/daemon_picker.py",
    ],
)
def test_user_facing_python_strings_have_no_milestone_leaks(rel_path: str) -> None:
    target = _REPO_ROOT / rel_path
    files = (
        sorted(target.rglob("*.py"))
        if target.is_dir()
        else [target]
    )
    leaks: list[str] = []
    for f in files:
        for lineno, lit in _scan_python(f):
            snippet = lit[:80].replace("\n", " ")
            leaks.append(f"{f.relative_to(_REPO_ROOT)}:{lineno}  {snippet}")
    assert not leaks, "milestone numbers leaked into user-facing strings:\n  " + "\n  ".join(leaks)


def test_locale_files_have_no_milestone_leaks() -> None:
    locale_dir = _REPO_ROOT / "src" / "veles" / "locales"
    if not locale_dir.is_dir():
        return
    leaks: list[str] = []
    for f in sorted(locale_dir.glob("*.toml")):
        for lineno, line in _scan_toml(f):
            leaks.append(f"{f.relative_to(_REPO_ROOT)}:{lineno}  {line}")
    assert not leaks, "milestone numbers leaked into locale files:\n  " + "\n  ".join(leaks)
